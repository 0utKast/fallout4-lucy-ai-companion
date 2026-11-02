"""Instant Pre-Cached Iconic Voice Barks (0.00s latency) for Lucy MacLean (100% Pure English Edition).

Includes Lucy's signature lines outside of live chat:
- "Okey-dokey, let's get to it!" (recruitment, follow orders, combat start)
- "All dispatched!" (Codsworth-style post-combat victory lines)
- Instant Companion Affinity reactions (Like, Love, Dislike, Hate, and Max Affinity Perk unlock)
- Vault 111 Exterior Overlook greeting & farewell lines
"""

import hashlib
import random
from pathlib import Path

HERE = Path(__file__).parent
BARKS_CACHE_DIR = HERE / "state" / "barks_cache_en"

BARKS_EN: dict[str, list[str]] = {
    "v111_greeting": [
        "Hey, over here! Okey-dokey, another real Vault Dweller! Come talk to me whenever you're ready, I tracked your pod's signal to Vault 111!",
        "Hello there, Vault 111 Dweller! I'm Lucy MacLean from Vault 33! Oh sugar, what a relief to meet someone who isn't trying to shoot me!",
    ],
    "recruited": [
        "Okey-dokey, let's get to it! You and me are going to make a terrific team out here in the Commonwealth!",
        "Okey-dokey, let's get to it! Vault 111 and Vault 33 working together—the Golden Rule in action!",
    ],
    "recruit_declined": [
        "Okey-dokey! I'll wait right here at the Vault 111 overlook keeping watch. Come back whenever you're ready to get to it!",
    ],
    "dismissed": [
        "Okey-dokey! I'll head back to my camp at the Vault 111 exterior overlook. Come get me whenever you want to get back to it!",
        "Understood! I'll wait for you at the Vault 111 overlook. Stay safe out there and remember the Golden Rule!",
    ],
    "follow_me": [
        "Okey-dokey, let's get to it!",
        "Okey-dokey! Right behind you, partner—let's get to it!",
        "Moving out! Okey-dokey, let's get to it!",
        "Ready when you are! Let's get to it!",
    ],
    "wait_here": [
        "Okey-dokey! I'll stay right here and guard the perimeter until you say the word.",
        "Got it! Waiting right here, Vault 111 partner.",
        "Okey-dokey! Holding this position. Just let me know when we're getting back to it!",
    ],
    "combat_start": [
        "Okey-dokey, let's get to it! Let's try not to lose any fingers this time!",
        "Oh sugar, hostiles incoming! Take cover, let's get to it!",
        "For Vault 33! Okey-dokey, let's get to it—strictly in self-defense!",
        "Goodness gracious, we're under attack! Let's get to it, I've got your back!",
    ],
    "combat_end": [
        "All dispatched! Okey-dokey, we made it through in one piece!",
        "Done and all dispatched! Though I am definitely going to need to wash my Vault 33 jumpsuit after that.",
        "Threat neutralized and all dispatched! That's the Golden Rule... applied in self-defense.",
        "Phew, all dispatched! Goodness, we make a really sharp team under pressure!",
        "All dispatched over here! Okey-dokey, not even a major scratch!",
    ],
    "companion_hurt": [
        "Oh sugar, I'm hit bad! I could really use a Stimpak!",
        "Goodness gracious, that hurts! A little medical assistance, please!",
    ],
    "companion_recovered": [
        "Phew, much better! Okey-dokey, I'm ready to get back to it!",
    ],
    "affinity_like": [
        "Okey-dokey! That was really neat—that's how a proper Vault Dweller gets things done!",
        "Nice work! The Vault 33 council would be super proud of your resourcefulness.",
        "I really like how you handle things, partner! Okey-dokey, keep it up!",
        "That was super helpful and constructive! Well done!",
    ],
    "affinity_love": [
        "Oh my goodness, that was wonderful! Traveling with you truly restores my faith in the surface and the Golden Rule.",
        "Okey-dokey, that was amazing! You're the exact kind of hero I used to read about back in Vault 33.",
        "What a noble thing to do! Traveling by your side is honestly the best thing that's happened to me since leaving Santa Monica.",
    ],
    "affinity_dislike": [
        "Oh sugar... I really didn't like that. That goes against Vault 33 community guidelines.",
        "Hey now, we really shouldn't be doing things like that if we're following the Golden Rule.",
        "Goodness gracious... back in Vault 33, the council would issue a formal reprimand for that.",
    ],
    "affinity_hate": [
        "Oh my gosh, stop! That was cruel and uncalled for! I didn't walk all the way from New Vegas to act like The Ghoul!",
        "That completely violates the Golden Rule! I cannot support hurting innocent people in cold blood!",
    ],
    "affinity_max_perk": [
        "Okey-dokey! After everything I went through with my dad Hank and Cooper Howard, you proved to me that the Golden Rule is still alive. You can count on me forever, partner!",
    ],
}

_last_picked: dict[str, str] = {}


def is_bark_event(event_name: str) -> bool:
    return event_name in BARKS_EN


def pick_bark_text(event_name: str) -> str | None:
    options = BARKS_EN.get(event_name)
    if not options:
        return None
    if len(options) == 1:
        return options[0]
    prev = _last_picked.get(event_name)
    candidates = [o for o in options if o != prev] or options
    chosen = random.choice(candidates)
    _last_picked[event_name] = chosen
    return chosen


def bark_cache_path(text: str, voice_name: str) -> Path:
    BARKS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(f"{voice_name}:en:{text}".encode("utf-8")).hexdigest()[:16]
    return BARKS_CACHE_DIR / f"{h}.wav"
