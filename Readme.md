# RPGDataFumbler二 (二: Ni / Two)

RPGDataFumblerNi (RPGDuFu2) follows mimics DazedMTL workflow.

## Supported Engines

- RPGMaker (json):
  - MV
  - MZ

## Who is it for? / Usage

This was born out of frustration of trying to wrangle with DazedMTL.  
Got tired of trying to use a local model endpoint / non-OAI one that I just said "Screw it, I'll make my own."

Most of the configuration is done in the `.toml` file with some sensible defaults enabled for __local model__ usage.

If you want to pay money to OAI (eww...) just use DazedMTL instead.

## Support

In general, no support is given. This project is purely out of selfish interest for me.

## User guide

Fill in the required items in the `.example` and then run it.

### Concurrency

It is possible to run multiple translations in tandem. By default (in the example config) this is set as `2`.

If you don't mind blowing your money, you can set it as high as you want. However there's diminishing returns.

Things that can be concurrent:

- Multiple events with a map file of a RPG Maker game.
- Multiple events with a common events of a RPG Maker game.

What cannot be concurrent:

- Items/Weapons/Armor/Enemies (They are represented as 1 "Container")

The reason why those cannot be represented is because those files are typically not much in size compared to events.

This concurrency limit is applied globally. If using the default of 2, 

## Developer Guide

Roughly this project is split into 2 parts:

1. Parsers
2. Translators

Parsers are what you would write to convert a game engine format into a json representation that is ready to be translated.  
See the system example of from the config.

Translators (Only OAI now) takes in the representations and translates the contents into whichever language you desire.

### OAICompatible Translator

This uses OAI text prompt to send messages. (Pretty self-explainatory.)

### Configuration

Read the comments in the `config.toml` file.

### Abstractions

There's a LOT of abstractions due to how complex it is. Please bear with it. I'll eventually cut down on it.

## Resources

- Consider either [KoboldCpp](https://github.com/LostRuins/koboldcpp) (GGUF) or [tabbyAPI](https://github.com/theroyallab/tabbyAPI) (EXL2) if you plan to run your models locally (Min 8GB).
- If you don't mind spending a bit, you can consider [featherless.ai](https://featherless.ai/).
- 

## Models

- I found `MarinaraSpaghetti/NemoMix-Unleashed-12B` to be quite good from model testing.
- ??? Probably add more.

## Credits

- [llm-prompt-templates](https://github.com/theroyallab/llm-prompt-templates) (MIT)