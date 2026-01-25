# Some Notes on use of Claude in the Project

## Intro

A few notes on giles experience with developing this project alsong side Claude.

I was using Claude Sonnet 4.5 and sometimes Claude Opus 4.5 inside of a $39/month Github Copilot subscription. VSCode was the IDE and I used the chat window mostly, with occasional use of auto complete.

## AGENTS.md

Its very useful to add some fixed context to the project source. I added an [AGENTS.md](AGENTS.md), this one describes how to use python copier template based python projects.

It also describes some domain specific knowledge about EtherCat and some of the more complex details of this repo's source code [here](AGENTS.md#domain-knowledge)

## Adding Skills

I added some skills to the AGENTS.md file using a prompt like this:

---

1. document your understanding of the XML file naming convention and schema - put it in a new md page in reference section
2. Use this document to add an agent skill so that I can load in that understanding at any time I want to (suggest a good set of prompts to load this skill)
3. go ahead and implement showing the composite types in the Symbols in the GUI instead of the constituent low level types
4. document your understanding of how the composite name types are constructed by twincat and how they are implemented in the code in a new explantations file intended as a compliment to the terminal-definitions document

---

## Repeated Issues

Sometimes the same problem keeps coming back. e.g. each time I asked Claude to look in the cached Beckhoff Terminal XML to ask about a terminal, it had to rediscover how to find and parse the XML files.

After working through something like this for the 2nd time, just prompt to put the understanding of this issue into the AGENTS.md, either in the [domain knowledge](AGENTS.md#domain-knowledge) section or as a new [skill](AGENTS.md#skills).

## Code Became too complex

At some point I started having problems with the XML parsing code. It had hit 12000 lines and Claude Sonnet was struggling to change it, in particular it kept re-introducing an indentation bug.

I asked Opus to take a look at the file and suggest a refactor. The results were simpler, broken into smaller modules and easier for Sonnet to understand.
