import pathlib
from typing import Any, List

import orjson
import tqdm
from loguru import logger

from FumblerLibrary.FumblerModels import TomlConfig, TranslationContainer

from .EventInterpreter import EVENTS_TYPES, EventInterpreter
from .EventsModels.EventCommon import EventChoice, EventText
from .RPGMVZModels import (
    Actor,
    Armor,
    Classes,
    CommonEvent,
    Enemy,
    Item,
    MapFile,
    Skill,
)


class MVMZParser:
    def __init__(self, files: list[pathlib.Path], config: TomlConfig) -> None:
        self.files = files
        self.parsed: list[tuple[pathlib.Path, Any]] = []
        self.parse_files()
        self.config = config

    def parse_files(self):
        for file in self.files:
            file = file.resolve()
            logger.info(f"Loading {file} with RPGM Loader...")
            try:
                json_data = orjson.loads(file.read_bytes())
            except orjson.JSONDecodeError:
                logger.warning(f"Decode error for: {file}")
                continue
            if isinstance(json_data, list) and len(json_data) >= 2:
                dict_item: dict = json_data[1]
                if "characterName" in dict_item:
                    logger.info(f"Detected {file} as ActorList.")
                    self.parsed.append(
                        (file, [Actor(**data) if data else None for data in json_data])
                    )
                elif "atypeId" in dict_item and "etypeId" in dict_item:
                    logger.info(f"Detected {file} as ArmorList.")
                    self.parsed.append(
                        (file, [Armor(**data) if data else None for data in json_data])
                    )
                elif "expParams" in dict_item and "learnings" in dict_item:
                    logger.info(f"Detected {file} as ClassesList.")
                    self.parsed.append(
                        (
                            file,
                            [Classes(**data) if data else None for data in json_data],
                        )
                    )
                elif "switchId" in dict_item and "trigger" in dict_item:
                    logger.info(f"Detected {file} as CommonEventsList.")
                    self.parsed.append(
                        (
                            file,
                            [
                                CommonEvent(**data) if data else None
                                for data in json_data
                            ],
                        )
                    )
                elif "battlerHue" in dict_item:
                    logger.info(f"Detected {file} as EnemyList.")
                    self.parsed.append(
                        (file, [Enemy(**data) if data else None for data in json_data])
                    )
                elif "consumable" in dict_item:
                    logger.info(f"Detected {file} as ItemsList")
                    self.parsed.append(
                        (file, [Item(**data) if data else None for data in json_data])
                    )
                elif "requiredWtypeId1" in dict_item:
                    logger.info(f"Detected {file} as SkillsList")
                    self.parsed.append(
                        (file, [Skill(**data) if data else None for data in json_data])
                    )
            elif isinstance(json_data, dict):
                if "autoplayBgm" in json_data:
                    logger.info(f"Detected MapFile: {file}")
                    self.parsed.append((file, MapFile(**json_data)))

    def _interp_event_list(self, events: List[EVENTS_TYPES]) -> dict[str, Any]:
        parsed_event_data: dict[str, Any] = {}
        for eventId, event in enumerate(
            EventInterpreter.decompile(events, self.config)
        ):
            if isinstance(event, EventText):
                if event.name:
                    text = [event.name, event.text]
                else:
                    text = event.text
                parsed_event_data[f"L_{str(eventId).zfill(2)}"] = text
            elif isinstance(event, EventChoice):
                parsed_event_data[f"L_{str(eventId).zfill(2)}"] = event.choices
        return parsed_event_data

    @staticmethod
    def get_full_mapping(
        translations: list[TranslationContainer | None], json: bool = False
    ):
        full_map = {}
        for tl in translations:
            if tl:
                full_map.update(tl.get_text_map)
        if json:
            remapped = {}
            for k, v in full_map.items():
                remapped[str(k)] = v
            full_map = remapped
        return full_map

    def apply_tl_containers(
        self,
        data: Any,
        translations: list[TranslationContainer | None],
    ):
        # Create a orig -> translated mappings

        if isinstance(data, MapFile):
            stats = {}
            text_maps = self.get_full_mapping(translations)
            for mapIdx, mapEvent in tqdm.tqdm(
                enumerate(data.events), desc="Map Events Processed"
            ):
                if not mapEvent:
                    continue
                # logger.debug(translations[mapIdx])
                for pageKey, pageData in enumerate(mapEvent.pages):
                    interpEvents = list(
                        EventInterpreter.decompile(pageData.list, self.config)
                    )
                    do_repack = False
                    for eventData in interpEvents:
                        # Apply Text
                        if (
                            isinstance(eventData, EventText)
                            and eventData.text in text_maps
                        ):
                            eventData.text = text_maps[eventData.text]
                            do_repack = True
                            stats["Text"] = stats.setdefault("Text", 0) + 1
                        # Text V2
                        elif (
                            isinstance(eventData, EventText)
                            and tuple([eventData.name, eventData.text]) in text_maps
                        ):
                            key = tuple([eventData.name, eventData.text])
                            tl_data = text_maps[key]
                            eventData.name = tl_data[0]
                            eventData.text = tl_data[1]
                            do_repack = True
                            stats["Text"] = stats.setdefault("Text", 0) + 1
                        # Apply Choices
                        elif (
                            isinstance(eventData, EventChoice)
                            and tuple(eventData.choices) in text_maps
                        ):
                            eventData.choices = list(
                                text_maps[tuple(eventData.choices)]
                            )
                            do_repack = True
                            stats["Choices"] = stats.setdefault("Choices", 0) + 1
                        else:
                            stats["?"] = stats.setdefault("?", 0) + 1
                        # TODO: Expand more here
                    if do_repack:
                        pageData.list = list(EventInterpreter.compile(interpEvents))
                        mapEvent.pages[pageKey] = pageData
                        data.events[mapIdx] = mapEvent
            logger.info(f"applied data: {stats}")
        elif isinstance(data, list) and len(data) >= 2:
            firstData = data[1]
            if isinstance(firstData, CommonEvent):
                text_maps = self.get_full_mapping(translations)
                for commonIdx, commonEvent in enumerate(data):
                    if not commonEvent:
                        continue
                    interpEvents = list(
                        EventInterpreter.decompile(commonEvent.list, self.config)
                    )
                    do_repack = False
                    for eventData in interpEvents:
                        if (
                            isinstance(eventData, EventText)
                            and eventData.text in text_maps
                        ):
                            logger.info("Applying Text")
                            eventData.text = text_maps[eventData.text]
                            do_repack = True
                        elif (
                            isinstance(eventData, EventText)
                            and tuple([eventData.name, eventData.text]) in text_maps
                        ):
                            logger.info("Applying Text Pair")
                            key = tuple([eventData.name, eventData.text])
                            tl_data = text_maps[key]
                            eventData.name = tl_data[0]
                            eventData.text = tl_data[1]
                            do_repack = True
                        # Apply Choices
                        elif (
                            isinstance(eventData, EventChoice)
                            and tuple(eventData.choices) in text_maps
                        ):
                            logger.info("Applying Choice")
                            eventData.choices = list(
                                text_maps[tuple(eventData.choices)]
                            )
                            do_repack = True
                    if do_repack:
                        commonEvent.list = list(EventInterpreter.compile(interpEvents))
                        data[commonIdx] = commonEvent
            elif isinstance(firstData, Item) and translations[0] is not None:
                tldata = translations[0].translated
                for itemidx, item in tqdm.tqdm(enumerate(data), desc="Items Processed"):
                    if not item or not itemidx not in tldata:
                        continue
                    do_proc = any([item.name, item.description, item.note])
                    if not do_proc:
                        continue
                    itemtl = translations[0].translated[f"IT_{str(itemidx).zfill(4)}"]
                    if len(itemtl) == 1:
                        logger.warning(f"Potentially invalid itemtl: {itemtl}")
                    if len(itemtl) == 2:
                        if item.name:
                            item.name = itemtl[0]
                        if item.description:
                            item.description = itemtl[1]
                        if item.note and item.description:
                            logger.warning(
                                "Detected collision of note and description."
                            )
                        else:
                            item.note = itemtl[1]
                            # ????
                    elif len(itemtl) == 3:
                        # For items it's as 1 translation container.
                        item.name, item.description, item.note = translations[
                            0
                        ].translated[f"IT_{str(itemidx).zfill(4)}"]
                    else:
                        logger.warning(f"{itemtl} has invalid count of items.")
                    data[itemidx] = item
        return data

    def prepare_tl_containers(
        self, data: Any
    ) -> list[TranslationContainer | None] | None:
        if isinstance(data, MapFile):
            # Map files
            map_events_list: list[TranslationContainer | None] = []
            for _, mapEvent in tqdm.tqdm(
                enumerate(data.events), desc="Map Events Processed"
            ):
                # Flatten page data to just a list of events for the map.
                if mapEvent:
                    for pageidx, page in enumerate(mapEvent.pages):
                        pageData = self._interp_event_list(page.list)
                        if pageData:
                            map_events_list.append(
                                TranslationContainer(tl_type="event", data=pageData)
                            )
                        else:
                            map_events_list.append(None)
                    else:
                        map_events_list.append(None)
                else:
                    map_events_list.append(None)
            return map_events_list
        elif isinstance(data, list):
            # List can mean anything so we check for the 2nd value.
            # 1st value in RPGM stuff is always null.
            if len(data) < 2:
                return []
            list_containers: list[TranslationContainer | None] = []
            if isinstance(data[1], CommonEvent):
                for _, commEvt in tqdm.tqdm(
                    enumerate(data), desc="Map Events Processed"
                ):
                    if not commEvt:
                        list_containers.append(None)
                        continue
                    pageData = self._interp_event_list(commEvt.list)
                    if pageData:
                        list_containers.append(
                            TranslationContainer(tl_type="event", data=pageData)
                        )
                    else:
                        list_containers.append(None)
                return list_containers
            elif isinstance(data[1], Item):
                main_container = TranslationContainer(tl_type="item", data={})
                for itemidx, item in tqdm.tqdm(enumerate(data), desc="Items Processed"):
                    if not item or not isinstance(item, Item):
                        list_containers.append(None)
                        continue
                    item_data = [item.name, item.description, item.note]
                    if any(item_data):
                        main_container.data[f"IT_{str(itemidx).zfill(4)}"] = item_data
                return [main_container]
