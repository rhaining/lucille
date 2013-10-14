import hipchat.config
from hipchat.room import Room
import json
import re
from httplib2 import Http
from urllib import urlencode
import random
import datetime
from dateutil import parser
import time
import urllib

hipchat.config.init_cfg('hipchat.cfg')

lucille_cfg_file = open('lucille.cfg')
lucille_cfg = json.load(lucille_cfg_file)
giphy_api_key = lucille_cfg.get("giphy_api_key",None)
hipchat_room_name = lucille_cfg.get("hipchat_room", None)
hipchat_room_names = lucille_cfg.get("hipchat_rooms", None)

if giphy_api_key == None:
  print "missing giphy_api_key in cfg"
  exit()

if hipchat_room_name == None and hipchat_room_names == None:
  print "missing hipchat_room in cfg"
  exit()

if hipchat_room_names == None:
  hipchat_room_names = [hipchat_room_name]

my_username = "lucille"

try:
  raw_hipchat_log=open('lucille.log')
  hipchat_log = json.load(raw_hipchat_log)
  raw_hipchat_log.close()
except Exception:
  hipchat_log = {};

hipchat_rooms = []
for r in Room.list():
  if r.name in hipchat_room_names:
    hipchat_rooms.append(r)

if len(hipchat_rooms) == 0:
  print "no room found for digg"
  exit()

GIPHY_REGEX = re.compile("\/giphy (.+)")

EIGHTBALL_COMMAND_TERM = "8ball"
EIGHTBALL_POSITIVE_RESPONSES = set(['It is decidedly so', 'Without a doubt', 'Yes definitely', 'It is certain', 'Most likely', 'You may rely on it', 'Yes', 'Outlook good', 'As I see it yes', 'Signs point to yes'])
EIGHTBALL_NEGATIVE_RESPONSES = set(['Cannot predict now', 'Reply hazy try again', 'Ask again later', 'Better not tell you now', 'Concentrate and ask again'])
EIGHTBALL_NEUTRAL_RESPONSES = set(['My reply is no', 'My sources say no', "Don't count on it", 'Very doubtful', 'Outlook not so good'])

EIGHTBALL_RESPONSE_TO_KEYWORDS = {
    'As I see it yes': ["reaction yes"],
    'Ask again later': ["sleeping"],
    'Better not tell you now': ["shocked"],
    'Cannot predict now': ["shrug"],
    'Concentrate and ask again': ["bored impatient"],
    "Don't count on it": ["unsure"],
    'It is certain': ["agree yes"],
    'It is decidedly so': ["yes yeah"],
    'Most likely': ["reaction yes"],
    'My reply is no': ["finger wag"],
    'My sources say no': ["shake head"],
    'Outlook good': ["thumbs up"],
    'Outlook not so good': ["suspicious"],
    'Reply hazy try again': ["thinking"],
    'Signs point to yes': ["yes nod"],
    'Very doubtful': ["eye roll"],
    'Without a doubt': ["yes thumbs up"],
    'Yes': ["yes nod"],
    'Yes definitely': ["yes yeah"],
    'You may rely on it': ["excited"]
}


# http://help.hipchat.com/knowledgebase/articles/64359-running-a-hipchat-bot
while True:
  last_message_times = hipchat_log.get("last_message_times",None)
  if last_message_times == None:
    _deprecated_last_message_time = hipchat_log.get("last_message_time",0)
    if _deprecated_last_message_time > 0:
      hipchat_log.pop("last_message_time",None)
      last_message_times = {}
      for hipchat_room in hipchat_rooms:
        last_message_times[hipchat_room.name] = _deprecated_last_message_time
        hipchat_log["last_message_times"] = last_message_times

  for hipchat_room in hipchat_rooms:
    terms = []
    last_message_time = last_message_times.get(hipchat_room.name, 0)

    most_recent_message_date = None

    try:
      recent_messages = Room.history(room_id=hipchat_room.room_id, date="recent")
    except Exception, e:
      print e
      time.sleep(20)
      continue

    for m in recent_messages:
      user = getattr(m, 'from')
      user_name = user.get('name')
      user_id = user.get('user_id',None)
      if user_id == "api" or user_name == my_username:
        continue

      try:
        message = getattr(m, 'message')
        message_date_string = getattr(m, 'date')
        message_date = parser.parse(message_date_string)
        message_time = time.mktime(message_date.timetuple())
        if message_time > last_message_time and message:
          term = GIPHY_REGEX.findall(message)
          if term:
            if most_recent_message_date:
              if most_recent_message_date > message_date:
                most_recent_message_date = message_date
            else:
              most_recent_message_date = message_date
            if message_time > last_message_time:
              terms.append(term[0])
      except AttributeError, e:
        print e
        pass

    if most_recent_message_date:
      most_recent_message_time = time.mktime(most_recent_message_date.timetuple())
      if hipchat_log.get("last_message_times",None) == None:
        hipchat_log["last_message_times"] = {}
      hipchat_log["last_message_times"][hipchat_room.name] = most_recent_message_time

    gif_urls = []
    no_results = []
    eightball_responses = []
    errors = []
    for t in terms:
      is_eightball_response = False
      eightball_response_message = None
      if t == EIGHTBALL_COMMAND_TERM:
        is_eightball_response = True
        #Pick a random 8ball response
        eightball_response_message = random.choice(EIGHTBALL_RESPONSE_TO_KEYWORDS.keys())
        #also replace the command term with an appropriate random giphy term
        t = random.choice(EIGHTBALL_RESPONSE_TO_KEYWORDS[eightball_response_message])

      encoded_t = urllib.quote_plus(t)
      print encoded_t
      url = "http://api.giphy.com/v1/gifs/search?q=%s&api_key=%s" % (encoded_t,giphy_api_key)
      print url
      h = Http()
      resp, content = h.request(url, "GET")
      gif_list = None
      try:
        gif_list = json.loads(content)
      except ValueError, e:
        print "error: %s" % e
        print "content: %s" % content
        continue
      data = gif_list.get("data", None)
      if data == None:
        #print url
        #print content
        data = gif_list.get("meta",None)
        if data != None:
          error_message = data.get("error_message",None)
          if error_message != None:
            errors.append("%s: %s" % (error_message, t))
            continue
        no_results.append(t)
        continue

      if data:
        count = len(data)
        if count == 0:
          no_results.append(t)
          continue
      else:
        no_results.append(t)
        continue
      random_index = random.randrange(count)
      gif_dict = data[random_index]
      images = gif_dict.get("images",None)
      if images:
        original_image = images.get("original", None)
        if original_image:
          original_image_url = original_image.get("url",None)
          if original_image_url:
            #Gif URL found
            if is_eightball_response and eightball_response_message:
              #Special case 8ball response
              if random.random() < 0.05: #5% of the time
                #EASTEREGG occasionally swap out image with dave winer gif
                original_image_url = 'http://f.cl.ly/items/2B2O014311012c1W3O0f/winer.gif'
                eightball_response_message = "Dave Winer says " + eightball_response_message

              eightball_responses.append((eightball_response_message, original_image_url))
            else:
              #normal lucille response (gif search)
              gif_urls.append(original_image_url)


    for url in gif_urls:
      print url
      # message_text = "%s: %s" % ()
      message = {'room_id': hipchat_room.room_id, 'from': my_username, 'message': url, 'message_format' : 'text', 'color' : 'green'}
      retval = Room.message(**message)
      print retval

    for eightball_response, eightball_response_gif in eightball_responses:
      eightball_message = "%s %s" % (eightball_response, eightball_response_gif)
      #determine a color based on the type of response
      if eightball_response in EIGHTBALL_POSITIVE_RESPONSES:
        eightball_color = 'green'
      elif eightball_response in EIGHTBALL_NEGATIVE_RESPONSES:
        eightball_color = 'red'
      else:
        eightball_color = 'yellow'

      message = {'room_id': hipchat_room.room_id, 'from': my_username, 'message': eightball_message, 'message_format' : 'text', 'color' : eightball_color}
      retval = Room.message(**message)


    if len(no_results):
      no_results_string = ", ".join(no_results)
      message_text = "No results for: %s" % no_results_string
      message = {'room_id': hipchat_room.room_id, 'from': my_username, 'message': message_text, 'message_format' : 'text', 'color': 'gray'}
      Room.message(**message)

    if len(errors):
      errors_string = "\n".join(errors)
      message_text = errors_string
      message = {'room_id': hipchat_room.room_id, 'from': my_username, 'message': message_text, 'message_format' : 'text', 'color': 'gray'}
      Room.message(**message)

  with open('lucille.log', 'w') as outfile:
    json.dump(hipchat_log, outfile)

  time.sleep(3)

