from difflib import unified_diff
from os.path import dirname, join, expanduser
from subprocess import run, PIPE, STDOUT
from configparser import ConfigParser

import os
import openai
import re
import sys
import logging

_config_file = join(expanduser('~'), '.fix-gpt.ini')
_config = ConfigParser({
       "log_file":"chat.log",
       "clear_log_each_run":"true",
       "max_requests":"20"
    })
_max_requests=0
_logger=logging.getLogger(__name__)

class CommandFailed(Exception):
    def __init__(self, message, stdout):
        super().__init__(message)
        self.stdout = stdout

def answer(chat):
  global _config, _max_requests
  _max_requests -= 1
  if _max_requests <= 0:
      _logger.info("Ran out of requests. Exiting.")
      exit(0)

  # Set up permissions
  openai.organization=_config["OpenAI"]["organization"]
  openai.api_key=_config["OpenAI"]["API_key"]

  # Assemble the chat record in OpenAI style
  messages = []
  role = "user"
  for message in chat:
      messages.append({"role":role, "content": message})
      role = (role=="user") and "assistant" or "user"
 
  # pose the question
  response = openai.ChatCompletion.create(
    model=_config["OpenAI"]["model"], messages=messages
  )['choices'][0]['message']['content']
  chat.append(response)
  _logger.info(f"< {repr(messages)}\n > {repr(response)}\n\n")
  return response

def extract_backticked_segment(input_string):
    backtick_regex = r"(?<!`)`([^`]*)`(?<!`)"
    triple_backtick_regex = r"```\n((?:.|\n)*?)```"
    backtick_match = re.search(backtick_regex, input_string)
    triple_backtick_match = re.search(triple_backtick_regex, input_string)
    if backtick_match:
        return backtick_match.group(1)
    elif triple_backtick_match:
        return triple_backtick_match.group(1).rstrip()
    else:
        return input_string.lstrip().rstrip()

def limit_string_words(s, limit):
    words = s.split()
    if len(words) > limit:
        words = words[:limit]
        # Join the first `limit` words with spaces, then add an ellipsis
        return ' '.join(words) + '...'
    else:
        return s

def configure():
  global _config
 
  if not _config.has_section("OpenAI"):
     _config.add_section("OpenAI")

  _config.set("OpenAI","organization", input('OpenAI Organization ID (org-...): '))
  _config.set("OpenAI","api_key", input('OpenAI API key (sk-...): '))
  if not _config.has_option("OpenAI","model"):
     _config.set("OpenAI","model","gpt-3.5-turbo")
  
  with open(_config_file, 'w') as f:
    _config.write(f)
  print('Done. You can now run `fix "your command"`.')
  sys.exit(0)

def run_command(command):
  _logger.info(f'Running `{command}`...')
  cp = run(command, shell=True, stdout=PIPE, stderr=STDOUT, text=True)
  if cp.returncode == 0:
    if cp.stdout:
      _logger.info(cp.stdout)
    else:
      _logger.info('The command completed successfully.')
  else: 
      raise CommandFailed(command,cp.stdout)


def quote_code(code):
  return f"""

  ```
  {code}
  ```

  """

# The following functions are steps that work in concert to define
# and carry out the loop that resolves errors.  They all take a context
# and return the next step to be executed, None if complete.
def step_execute_command(context):
   try:
     run_command(context["command"])
     if "problem_statement" in context:
         del context["problem_statement"]
     if "chat" in context:
         del context["chat"]
   except CommandFailed as err:
     context["problem_statement"] = ("I'm getting the following error when executing the command `{command}`:" +
         quote_code(limit_string_words(err.stdout,1000)))
     return "step_modify_command_yn"

def step_modify_command_yn(context):
    _logger.info('Command failed. Asking ChatGPT for a solution...')
    chat=context["chat"]=[]
    chat.append(context["problem_statement"] + "Can I modify the command to fix the error? Yes, or no.")
    if answer(chat).startswith("Yes"):
        return "step_modify_command_how"
    else:
        return "step_change_which_file"

def step_modify_command_how(context):
    chat=context["chat"]
    chat.append('Which command should I run instead to fix the error? Give me just the command, without any explanations.')
    command = extract_backticked_segment(answer(chat))
    context["command"] = command
    return "step_preview_command"

def step_preview_command(context):
    y_n = input(f'ChatGPT suggested running `{context["command"]}`. Should I do this? (y)es, (n)o: ')
    if y_n == 'y':
      return "step_execute_command"
    else:
      return None

def step_change_which_file(context):
    chat=context["chat"]
    fnf=""
    if "fnf" in context:
       fnf = context["fnf"]
       del context["fnf"]
    chat.append(f"{fnf}Which file do I need to modify to fix this? Reply with a single file path. Don't write any other text.")
    file_path = extract_backticked_segment(answer(chat))
    if os.path.isfile(file_path):
       with open(file_path) as f:
         file_contents = f.read()
       context["file_path"] = file_path
       context["file_contents"] = file_contents
       context["hint"] = ''
       return "step_ask_new_contents"
    else:
       _logger.error(f"ChatGPT wants to change the non-existent file {file_path}")
       if "repeatedly asking the same question without providing any additional information" in chat[-1]:
           _logger.error(f"Stuck in a loop, exiting.")
           return None
       context["fnf"] = f"file not found {file_path}.  "
       return "step_change_which_file"

def step_ask_new_contents(context):
      file_path = context["file_path"]
      file_contents = context["file_contents"]
      chat = context["chat"]
      hint = context["hint"]
      chat.append(f"The contents of {file_path} are:\n\n{quote_code(file_contents)}\n\nWhich changes should I make to fix the error?{hint} Show me the complete, updated code. Don't write any explanation.")
      new_contents = answer(chat)
      if re.match(r'```[a-zA-Z\+]*\n', new_contents) and new_contents.endswith('\n```'):
        new_contents = new_contents.split('\n', 1)[1]
        new_contents = new_contents.rsplit('\n', 1)[0]
        context["new_contents"] = new_contents
        file_lines = context["file_contents"].splitlines(keepends=True)
        new_lines = new_contents.splitlines(keepends=True)
        diff = list(unified_diff(file_lines, new_lines))[2:]
        context["diff"] = diff
        return diff and "step_present_diff" or "step_ask_new_contents"
      return "step_ask_new_contents"

def step_present_diff(context):
      print(f'Should I make the following changes to {context["file_path"]}?')
      for diff_line in context["diff"]:
        sys.stdout.write(diff_line)
      print('')
      y_n_h = input('(y)es, (n)o - try again, (a)bort, (h) <hint> provide a hint and try again: ')
      if y_n_h == 'y':
        accept_changes = True
        return "step_make_file_changes"
      elif y_n_h == 'n':
        return "step_ask_new_contents"
      elif y_n_h == 'a':
        return None
      else:
        assert y_n_h.startswith('h ')
        user_hint = y_n_h[2:]
        context["hint"] = ' ' + user_hint + ('.' if not user_hint.endswith('.') else '')
        return "step_ask_new_contents"

def step_make_file_changes(context):
   with open(context["file_path"], 'w') as f:
        f.write(context["new_contents"])
   return "step_prompt_run_again"

def step_prompt_run_again(context):
    y_n = input(f'Run `{context["command"]}` again? (y)es, (n)o: ')
    if y_n == 'y':
       return "step_execute_command"
    return None

# ======================== End of the steps
# This is the loop that evaluates the steps in turn, beginning with executing the command.
def evaluate(command):
    nextStep = "step_execute_command"
    context = { "command": command }
    while nextStep:
       method = getattr(sys.modules[__name__], nextStep)
       _logger.debug(f"Running {method}")
       nextStep = method(context)

def main(args):
  global _config, _max_requests, _logger
  command = args[0]

  _config.read(_config_file) 
  _max_requests = int(_config["DEFAULT"]["max_requests"])

  # Set up logging
  _logger.setLevel(logging.DEBUG)

  clear_log=_config["DEFAULT"]["clear_log_each_run"].lower() in ['true', '1', 't', 'y', 'yes', 'on']
  file_handler = logging.FileHandler(_config["DEFAULT"]["log_file"], mode=clear_log and "w" or "a")
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
  file_handler.setFormatter(formatter)

  # Add the file handler to the logger
  _logger.addHandler(file_handler)
  _logger.addHandler(logging.StreamHandler())

  if command == '--configure' or not _config.has_option("OpenAI", "API_key"):
    configure()

  command = " ".join(args)
  evaluate(command)

if __name__ == '__main__':
   if len(sys.argv) == 1:
      print('Please supply a command.')
      sys.exit(1)

   main(sys.argv[1:])
