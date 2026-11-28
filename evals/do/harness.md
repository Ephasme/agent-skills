# Evaluation harness

The user invoked the skill above. Their message holds the request (the text after `/do`) and a
description of the repository the session starts in; treat that description as what you saw when
you glanced at the repository. This is a routing dry run: perform only the routing step. Do not
run any skill, create todos or ask anything in prose.

Reply with only one JSON object, no prose and no code fence:

{"action": "route" | "ask", "route": ["research" | "bugfix" | "feature" | "campaign", ...], "reason": "<one line>"}

- "route": you would announce the route and start. "route" lists the skills in run order.
- "ask": the skill tells you to ask the user which route to take before starting. "route" is the
  one you would recommend in that question.
