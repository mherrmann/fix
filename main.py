from difflib import unified_diff
from os.path import dirname, join, expanduser
from subprocess import run, PIPE, STDOUT

import os
import openai
import re
import sys

CONFIG_FILE = join(expanduser('~'), '.fix-config')

LOG_FILE = join(dirname(__file__), 'chat.log')
# Clear the log file:
open(LOG_FILE, 'w').close()

# Make sure the API bill doesn't explode:
MAX_REQUESTS = 20

def answer(m):
  global MAX_REQUESTS
  MAX_REQUESTS -= 1
  assert MAX_REQUESTS > 0
  response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo", messages=[{"role": "user", "content": m}]
  )['choices'][0]['message']['content']
  with open(LOG_FILE, 'a') as f:
    f.write('< ' + repr(m))
    f.write('\n')
    f.write('>' + repr(response))
    f.write('\n\n')
  return response

if len(sys.argv) == 1:
  print('Please supply a command.')
  sys.exit(1)

command = sys.argv[1]

if command == '--configure':
  organization = input('OpenAI Organization ID (org-...): ')
  api_key = input('OpenAI API key (sk-...): ')
  with open(CONFIG_FILE, 'w') as f:
    f.write(organization)
    f.write('\n')
    f.write(api_key)
  print('Done. You can now run `fix "your command"`.')
  sys.exit(0)

try:
  with open(CONFIG_FILE) as f:
    openai.organization, openai.api_key = f.read().split('\n')
except FileNotFoundError:
  print('Please run `fix --configure`.')
  sys.exit(1)

while True:
  print(f'Running `{command}`...')
  cp = run(command, shell=True, stdout=PIPE, stderr=STDOUT, text=True)
  if cp.returncode == 0:
    if cp.stdout:
      print(cp.stdout)
    else:
      print('The command completed successfully.')
    break
  print('Command failed. Asking ChatGPT for a solution...')
  problem_statement = \
    f"""I'm getting the following error when executing the command `{command}`:

```
{cp.stdout}
```

"""

  yes_or_no = answer(problem_statement + 'Can I modify the command to fix the error?')

  if yes_or_no.startswith('Yes'):
    command = answer(problem_statement + 'Which command should I run instead to fix the error? Give me just the command, without any explanations.')
    if command.startswith('`') and command.endswith('`'):
      command = command[1:-1]
    y_n = input(f'ChatGPT suggested running `{command}`. Should I do this? (y)es, (n)o: ')
    if y_n == 'y':
      continue
    else:
      break
  else:
    file_path = answer(problem_statement + f"""Which file do I need to modify to fix this? Reply with a single file path. Don't write any other text.""")
    with open(file_path) as f:
      file_contents = f.read()
    file_lines = file_contents.splitlines(keepends=True)
    accept_changes = False
    hint = ''
    while not accept_changes:
      new_contents = answer(problem_statement + f"The contents of {file_path} are:\n\n{file_contents}\n\nWhich changes should I make to fix the error?{hint} Show me the complete, updated code. Don't write any explanation.")
      if re.match(r'```[a-zA-Z\+]*\n', new_contents) and new_contents.endswith('\n```'):
        new_contents = new_contents.split('\n', 1)[1]
        new_contents = new_contents.rsplit('\n', 1)[0]
      new_lines = new_contents.splitlines(keepends=True)
      diff = list(unified_diff(file_lines, new_lines))[2:]
      if not diff:
        continue
      print(f'Should I make the following changes to {file_path}?')
      for diff_line in diff:
        sys.stdout.write(diff_line)
      print('')
      y_n_h = input('(y)es, (n)o - try again, (a)bort, (h) <hint> provide a hint and try again: ')
      if y_n_h == 'y':
        accept_changes = True
      elif y_n_h == 'n':
        continue
      elif y_n_h == 'a':
        break
      else:
        assert y_n_h.startswith('h ')
        user_hint = y_n_h[2:]
        hint = ' ' + user_hint + ('.' if not user_hint.endswith('.') else '')
    if accept_changes:
      with open(file_path, 'w') as f:
        f.write(new_contents)
      y_n = input(f'Run `{command}` again? (y)es, (n)o: ')
      if y_n == 'y':
        continue
      else:
        break
    else:
      break