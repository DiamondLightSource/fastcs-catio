# Some Notes on use of Claude in the Project

## Intro

A few notes on giles experience with developing this project along side Claude.

I was using Claude Sonnet 4.5 and sometimes Claude Opus 4.5 inside of a $39/month Github Copilot subscription. VSCode was the IDE and I used the chat window mostly, with occasional use of auto complete.

## AGENTS.md

Its very useful to add some fixed context to the project source. I added an [AGENTS.md](AGENTS.md), this one describes how to use python copier template based python projects.

It also describes some domain specific knowledge about EtherCat and some of the more complex details of this repo's source code in the [domain knowledge section](./AGENTS.md#domain-knowledge).

This is one of the standard places that CoPilot looks for context and works with all the models. It also works for Copilot running in the cloud for PR reviews etc.

Read about this in the [Github Blog](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/).

## Repeated Issues

Sometimes the same problem keeps coming back. e.g. each time I asked Claude to look in the cached Beckhoff Terminal XML to ask for details about an EtherCat terminal type, it had to rediscover how to find and parse the XML files and took several attempts to get it right.

After working through something like this for the 2nd time, just prompt to put the understanding of this issue into the AGENTS.md, either in the [domain knowledge](AGENTS.md#domain-knowledge) section or as a new [skill](AGENTS.md#skills).


## Adding Skills

I added some skills to the AGENTS.md file using a prompt like this:

1. document your understanding of the XML file naming convention and schema - put it in a new md page in reference section
2. Use this document to add an agent skill so that I can load in that understanding at any time.(suggest a good set of prompts to load this skill)

See the [skills section](AGENTS.md#skills) of AGENTS.md for the results.


## Code Became too complex

(I mean, you should be doing this anyway but ...)

At some point I started having problems with the XML parsing code. It had hit 12000 lines and Claude Sonnet was struggling to change it, in particular it kept re-introducing an indentation bug.

I asked Opus to take a look at the file and suggest a refactor. The results were simpler, broken into smaller modules and easier for Sonnet to understand.

## Adding Complicated Features

I found it useful to get the agent to write a document for the feature first, review that, and then implement around that.

e.g. when implementing Beckhoff ADS Composite Types, I prompted something like this:

1. how does the EtherCat Master generate composite types from the set of primitive types each terminal provides?
1. document the details you have just described in the reference section
1. suggest an additional YAML file that describes the composite types, allowing us to generate the composite types from the primitive types
1. document that YAML and how it relates to the terminal definitions in an explanations file
1. using the above, implement the code to read that YAML and create the YAML file that contains describes the known composite types that you have already found
1. using the above, add code in catio_terminals to replace each group of primitive type symbols with the single composite type symbol that represents them


## Just Ask

Whatever question you can think of Claude is likely to have an OK answer. Whenever you are struggling, just ask the agent, I repeatedly forgot to do this in early interactions with coding agents!

e.g.:

- **user**: why do you keep having difficulty seeing the terminal output?
- **claude**:

    I see the issue now. When I use run_in_terminal, the tool result shows only # followed by a timestamp, but the actual output is available via terminal_last_command. This appears to be because:

    The run_in_terminal tool returns immediately with a minimal acknowledgment
    The actual command output is captured separately and accessible via terminal_last_command
- **user**: Please update agents.md with information about the run_in_terminal issue
- **claude**:

    Added a new "Terminal Tool Usage" section to AGENTS.md documenting that:

    run_in_terminal may not show output directly in its result
    Agents should use terminal_last_command to retrieve actual output
    Check exit codes in context before assuming failure

Another example: you have heard about skills but have no idea how to implement them. The agent knows how.
