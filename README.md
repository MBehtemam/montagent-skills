# Montagent skills

Agent skills for driving Montagent from any Agent-Skills-compatible client. Install them with:

```sh
npx skills add MBehtemam/Montagent
```

Start with `montagent`, the router skill. It points to the job skills: `montagent-motion`, `montagent-footage`, `montagent-character`, `montagent-prerender` and `montagent-craft`.

## Using the skills

Skills teach your coding agent how to drive Montagent; install the Montagent CLI separately using [the main README](../README.md). The CLI should be on the agent's PATH. The Montagent MCP server is optional when the agent has shell access.

To use the edited skills from this checkout before they are published, run the skill installer from your video project's directory and select the Montagent skills:

```sh
npx skills add /path/to/Montagent --skill montagent montagent-motion montagent-craft montagent-footage montagent-character montagent-prerender
```

Replace the local path with your own checkout path. The GitHub install command above gets the published repository version, which includes local edits only after they are pushed. Follow the installer's client selection, then reload your client's skill list if needed.

Ask your agent:

> Use montagent and montagent-motion to create a 10-second product intro, 1920×1080 at 30 fps. Use my logo and brand colors, reveal the headline, show one benefit, and finish with a readable logo hold. Save an editable Montagent project and render and verify the MP4.

Or, for an existing project:

> Use montagent-motion to improve the title entrance in intro.montagent.json. Preserve the copy and duration, preview the change, then render and verify it.

Clients with a skill picker let you explicitly select the named skills. Otherwise name them in the prompt. Start with the router; it loads the job guidance and craft checks as needed. Motion creative direction and recipes are bundled references, so you do not install them separately. These skills do not require Hyperframes.

## Experimental

These skills are experimental. A pre-registered, blind-judged eval on held-out briefs found **parity but no lift**:

- **Parity passed.** Opus 5.5 using Montagent with the skills was judged as good as Opus 5.5 working without Montagent. The no-Montagent reference won 2 of 9 pairs, against a limit of 40%.
- **Lift failed.** Montagent with the skills was not judged better than Montagent without them. With the skills won 4 pairs, without them won 6, and 17 were equal.

See [Verdict runs: every arm on the held-out briefs, judged blind](https://github.com/MBehtemam/Montagent/issues/549). A second verdict on new held-out briefs ran every arm but was closed as inconclusive, so the lift claim is dropped: the skills make no claim to produce better videos than Montagent without them. See [Second verdict runs: every arm on the new briefs, judged blind](https://github.com/MBehtemam/Montagent/issues/582).

The skills describe the main branch. If your installed `montagent` binary is older, trust its findings over the skills.
