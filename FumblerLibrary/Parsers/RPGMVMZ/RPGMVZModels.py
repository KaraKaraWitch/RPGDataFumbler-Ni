from typing import List, Optional

from pydantic import BaseModel

from .EventsModels.EventBase import EventBase


class Trait(BaseModel):
    code: int
    dataId: int
    value: int


class Actor(BaseModel):
    battlerName: str
    characterIndex: int
    characterName: str
    classId: int
    equips: List[int]
    faceIndex: int
    faceName: str
    id: int
    initialLevel: int
    maxLevel: int
    name: str
    nickname: str
    note: str
    profile: str
    traits: List[Trait]


class Page(BaseModel):
    conditions: dict
    directionFix: bool
    image: dict
    list: List[EventBase]
    moveFrequency: int
    moveRoute: dict
    moveSpeed: int
    moveType: int
    priorityType: int
    stepAnime: bool
    through: bool
    trigger: int
    walkAnime: bool


class Events(BaseModel):
    id: int
    name: str
    note: str
    pages: List[Page]
    x: int
    y: int


class CommonEvent(BaseModel):
    id: int
    list: List[EventBase]
    name: str
    switchId: int
    trigger: int


class Enemy(BaseModel):
    id: int
    actions: List[dict]
    battlerHue: int
    battlerName: str
    dropItems: List[dict]
    exp: int
    traits: List[dict]
    gold: int
    name: str
    note: str
    params: List[int]


class Item(BaseModel):
    id: int
    animationId: int
    consumable: bool
    damage: dict
    description: str
    effects: List[dict]
    hitType: int
    iconIndex: int
    itypeId: int
    name: str
    note: str
    occasion: int
    price: int
    repeats: int
    scope: int
    speed: int
    successRate: int
    tpGain: int


class Skill(BaseModel):
    id: int
    animationId: int
    damage: dict
    description: str
    effects: List[dict]
    hitType: int
    iconIndex: int
    message1: str
    message2: str
    mpCost: int
    name: str
    note: str
    occasion: int
    repeats: int
    requiredWtypeId1: int
    requiredWtypeId2: int
    scope: int
    speed: int
    stypeId: int
    successRate: int
    tpCost: int
    tpGain: int


class Armor(BaseModel):
    id: int
    atypeId: int
    description: str
    etypeId: int
    traits: List[Trait]
    iconIndex: int
    name: str
    note: str
    params: List[int]
    price: int


class LearnSkill(BaseModel):
    level: int
    note: str
    skillId: int


class Classes(BaseModel):
    id: int
    expParams: List[int]
    traits: List[Trait]
    learnings: List[LearnSkill]
    name: str
    note: str
    params: List[List[int]]


# File stuff


class MapFile(BaseModel):
    autoplayBgm: bool
    autoplayBgs: bool
    battleback1Name: str
    battleback2Name: str
    bgm: dict
    bgs: dict
    disableDashing: bool
    displayName: str
    encounterList: List
    encounterStep: int
    height: int
    note: str
    parallaxLoopX: bool
    parallaxLoopY: bool
    parallaxName: str
    parallaxShow: bool
    parallaxSx: int
    parallaxSy: int
    scrollType: int
    specifyBattleback: bool
    tilesetId: int
    width: int
    data: List[int]
    events: List[Optional[Events]]


# Lists are just RootModels
