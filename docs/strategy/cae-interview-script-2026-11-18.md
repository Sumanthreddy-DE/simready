# CAE engineer interview script (2026-11-18)

**Status:** active
**Last verified:** 2026-11-18

Purpose: find out where simulation engineers lose time and trust, before building anything
past SP3. Tests the parked FE-model checker idea (README § Parked direction) and checks
whether checker-scored AI CAD matters to people who use simulation results.

Rules for every call (Mom Test):
- Ask about the past, never about the future. "When did that last happen?" beats "Would you use…?"
- Never pitch SimReady or the checker idea during the questions. Show it only in the last 5
  minutes, and only if they ask.
- Ask for specifics: the last model, the last mistake, the hours, the tool.
- Compliments and "sounds useful" are not data. Money, time already spent, and workarounds
  already built are data.

Length: 25–30 minutes. Take notes in the log template at the bottom straight after the call.

## Outreach message

English:

> Hi <first name>, I'm a computational engineer (MSc Computational Engineering, FAU) researching how
> simulation engineers prepare and check FE models. Could I ask you about your workflow for
> 25 minutes? I'm not selling anything; I'm trying to understand where the time actually goes.
> Happy to share what I learn across all interviews afterwards.

German:

> Hallo <Vorname>, ich bin Computational Engineer (MSc Computational Engineering, FAU) und
> untersuche, wie Berechnungsingenieure FE-Modelle aufbauen und prüfen. Hätten Sie 25 Minuten
> für ein Gespräch über Ihren Arbeitsablauf? Ich verkaufe nichts, ich möchte verstehen, wo die
> Zeit tatsächlich hingeht. Die Ergebnisse aller Gespräche teile ich gern mit Ihnen.

## Questions

**Context (3 min)**
1. What do you simulate, in which industry, with which tools (pre-processor, solver)?
2. Roughly how many models do you or your team build per month? How big are they?

**Where the time goes (8 min)**
3. Walk me through the last model you built, from CAD to result. Which step took longest?
4. How long did geometry preparation take on that model (cleanup, defeaturing, mid-surfaces)?
   Is that typical?
5. What part of model setup do you hand to someone else, script, or outsource? Why that part?

**Where trust breaks (10 min) — tests H1**
6. Tell me about the last time a simulation result was wrong because of a setup mistake.
   What was the mistake? How was it found? What did it cost (runs, days, a decision)?
7. What do you check before you start a solve? Is that written down anywhere, or in your head?
8. Who reviews your models? What do they look for?
9. Have you or your colleagues let an AI tool (ChatGPT, Claude, Copilot, a vendor assistant)
   set up or change a model? What happened? Where did it go wrong?

**Tools and money (5 min) — tests H2, H3**
10. Which pre-processor features do you depend on most? What do you still do by hand anyway?
11. Have you bought or built anything to speed up setup or checking (scripts, macros, plugins)?
    Who paid, and how much effort was it?
12. Could your models be sent to a cloud tool, or must everything stay on your machines?

**Close (2 min)**
13. Who else should I talk to about this?
14. Can I come back to you in a few weeks with what I learned?

## Kill rules (from the evidence brief)

- H1: fewer than 3 of 10–15 interviewees describe a setup error that cost a run or a wrong
  decision in the last 3 months → drop the FE-model checker idea.
- H2: most interviewees say their pre-processor already handles geometry cleanup → drop
  geometry-cleanup products.
- H3: record the cloud answer in every interview; a majority "must stay local" makes
  local-only a hard requirement.

## Where to find interviewees

No names here; build the list from these channels.
- FAU: Computational Engineering alumni, chairs with FE research, the FAU racing team's
  simulation members.
- LinkedIn: "Berechnungsingenieur", "CAE Engineer", "FEM Simulation" at Mittelstand firms
  and engineering service providers in Bavaria and Baden-Württemberg.
- CAE service providers: they do pre-processing for others and know the pain from both sides.
- r/fea and r/CFD: reply to people who posted about setup or validation problems in the last
  90 days (read-only research so far; any outreach goes from your own account).

Target mix: at least 4 automotive or supplier, 3 Mittelstand machinery, 2 service providers,
2 who already use AI tools in their workflow.

## Log template (one block per interview)

```
### <date> — <role>, <industry>, <company size>
Tools: <pre-processor / solver>
Longest step on last model: <step, hours>
Last setup error: <what, how found, cost>  → H1 yes / no
Pre-processor handles cleanup: yes / partly / no  → H2
Cloud allowed: yes / no / depends  → H3
AI tools tried: <what, outcome>
Workarounds built or bought: <what, effort>
Quote worth keeping: "<verbatim>"
Referrals: <names or roles>
```
