# A local Python PF2e encounter engine

## The plan in plain language

Build a Python program that can run a complete tactical fight, explain its results, and resume a saved fight. A small terminal program lets a person use it without writing Python. Scripts and tests call the same engine directly.

Keep correctness firm within the supported game. Limit the available content and environments when necessary. Prefer a small working implementation over infrastructure designed for hypothetical future abilities.

S1–S3 and the S3i encounter expansion are implemented, independently reviewed, and enabled for local play. S3i adds eight S2 and eight S3 encounters, bringing the catalog to 21 setups. The full suite passes 211 tests. The active S3i extension targets all sixteen Player Core 1/2 classes at level 1, then level 2, using representative subclasses and small common content menus. Selected options must be correct and playable; exhaustive subclass or nested-choice coverage is not required. [STATUS](../../STATUS.md) records the latest progress; the [work log](../work-log/README.md) records decisions and delegated work.

## Plan index

1. **This document:** what we are building and how a person uses it.
2. [Engine and content](02-engine-and-content.md): the main components and how content uses shared rules.
3. [Rules and stages](03-rules-and-stages.md): source policy, rule families, content families, and successive runnable releases.
4. [Delivery and checks](04-delivery-and-checks.md): assignments, model routing, review, modular tests, process cleanup, performance, and usage records.
5. [Interaction encounters](05-interaction-encounters.md): the completed first S3i increment and its evidence.
6. [Class and content expansion](06-class-and-content-expansion.md): the active S3i extension, level-1/2 coverage, content selection and acceptance.

## Product decisions

- One local process owns an encounter. There is no browser, server, account system, or network synchronization.
- A person controls every creature initially. Enemy automation can later submit the same commands; it is not an engine prerequisite.
- Dice roll automatically. Tests can supply exact rolls, and a seed makes a new encounter reproducible.
- Start with fixed reviewed builds and encounters, not a character builder or an unrestricted content importer.
- Author content and starting encounters in Python. Store saved fights in JSON.
- Use ordinary scrolling terminal output, numbered choices, and coordinate input. Do not build a full-screen terminal framework or a natural-language interpreter.
- Campaign management, exploration, downtime, social systems, crafting, multiplayer, and visual rendering are outside the first product.

These choices implement the user's local-engine direction. They do not require further approval. A material change to that direction should be raised as a product decision.

## Playing a fight

The entry point is `python -m pf2e play <encounter>`. [README](../../README.md) gives the verified setup and current encounter commands. S1–S3 implement the interface capabilities below within their documented content and rules boundaries.

The terminal displays a small coordinate map, the active creature, HP, conditions, and remaining actions. The user chooses an action, then the relevant target, path, or other input. The engine reports the roll, relevant modifiers, degree of success, damage, and resulting changes.

Useful controls are: inspect, take an action, answer or decline a reaction, end turn, save, load, restart, and quit. Movement accepts an explicit path; any later destination shortcut must show the selected route when the route matters.

Ask for the next decision, not a complete preplanned turn. An activity that costs two actions is one request. Its internal steps can pause for a reaction and resume after that decision. A reaction prompt can belong to someone other than the creature taking its turn.

An encounter ends when one team has no conscious living creature able to keep fighting. This does not mean every opponent died. An unconscious ally can still be healed while its conscious teammates keep the encounter active. This documented end-of-fight policy is implemented and independently tested in S3i; between-encounter recovery remains outside the current runner.

The terminal formats results and input. It never calculates MAP, spends actions, refreshes resources, applies conditions, or decides health outcomes itself.

## Calling the engine from Python

The public interface should remain small:

| Operation | Meaning |
|---|---|
| `Encounter.start(setup, ...)` | Validate and initialize a new encounter. |
| `inspect(...)` | Read the current state or a focused rules explanation without changing anything. |
| `options(...)` | Ask for relevant actions or targets for the current decision. |
| `execute(command)` | Resolve one action, activity, or end-turn request. |
| `choose(prompt_id, option)` | Answer the currently pending choice. |
| `save(path)` / `Encounter.load(path, ...)` | Save or restore a fight already in progress. |

Scripts, tests, and the terminal use this same boundary. The current engine starts catalogued setups and rejects altered/ad hoc variants; adding a new encounter means authoring and registering its Python definition, then testing it. There is no second service API to keep equivalent.

An action returns a completed result, a committed pause awaiting a choice, an illegal-input explanation, or an unsupported-operation explanation. Output events describe what happened; they are not another rules language.

## What “supported” means

The program lists the exact available builds, creatures, abilities, basic actions, and environments. It does not claim whole-class or whole-book support because one build works.

Keep three boundaries visible:

- **Prototype limitations:** universal or common combat rules still missing from an experimental build.
- **Unavailable content:** a spell, feat, creature, or optional mode the program does not offer.
- **Enforced environment:** for example, grounded creatures on a bright flat map, which avoids unsupported flight or darkness interactions.

A mandatory rule of offered content cannot be silently discarded. If a creature brings an expensive ability, implement it or choose another creature. A synthetic test actor may prove execution without pretending to be a complete published creature.

The first success is a complete terminal encounter. The next is an encounter with reviewed content and all applicable advertised rules. Every later increment adds useful decisions to that same runnable program.
