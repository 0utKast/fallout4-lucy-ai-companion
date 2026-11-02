"""Frases icónicas instantáneas (Barks pre-cacheados con latencia 0.00s) para Lucy MacLean (Edición Español).

Incluye las expresiones clásicas de Lucy fuera del chat libre:
- "¡Oki-doki, vamos al lío!" (al reclutarla, iniciar marcha o entrar en combate)
- "¡Todo despachado!" al estilo Codsworth tras terminar un combate
- Reacciones inmediatas de Afinidad (Le gusta, Le encanta, No le gusta, Odia, y Ventaja de Afinidad Máxima)
- Saludo e historia en la explanada exterior del Refugio 111
"""

import hashlib
import random
from pathlib import Path

HERE = Path(__file__).parent
BARKS_CACHE_DIR = HERE / "state" / "barks_cache_es"

BARKS_ES: dict[str, list[str]] = {
    "v111_greeting": [
        "¡Eh, aquí! ¡Oki-doki, otro morador de Refugio! ¡Acércate cuando puedas, he captado la señal de tu cápsula desde el Refugio 111!",
        "¡Hola, morador del Refugio 111! ¡Soy Lucy MacLean, del Refugio 33! ¡Qué alegría ver a alguien que no intenta dispararme!",
    ],
    "recruited": [
        "¡Oki-doki, vamos al lío! Ya verás qué buen equipo hacemos por la Commonwealth aplicando la Regla de Oro.",
        "¡Oki-doki, vamos al lío! ¡Un morador del Refugio 111 y una del Refugio 33 juntos, esto va a salir genial!",
    ],
    "recruit_declined": [
        "¡Oki-doki! Me quedaré aquí mismo en la explanada del Refugio 111 vigilando el perímetro. ¡Vuelve cuando quieras que vayamos al lío!",
    ],
    "dismissed": [
        "¡Oki-doki! Volveré a nuestro campamento en la explanada exterior del Refugio 111. ¡Pásate a buscarme cuando quieras que volvamos al lío!",
        "¡Entendido! Te espero en la explanada del Refugio 111. ¡Ten mucho cuidado ahí fuera y recuerda la Regla de Oro!",
    ],
    "follow_me": [
        "¡Oki-doki, vamos al lío!",
        "¡Oki-doki! Vamos al lío, te cubro las espaldas.",
        "¡En marcha! ¡Oki-doki, vamos al lío!",
        "¡Listos para continuar! ¡Vamos al lío, compañero!",
    ],
    "wait_here": [
        "¡Oki-doki! Me quedo aquí mismo vigilando el perímetro hasta que me avises.",
        "¡Entendido! Espero aquí tranquilamente, compañero del Refugio 111.",
        "¡Oki-doki! No me moveré de este sitio. ¡Avisa cuando volvamos al lío!",
    ],
    "combat_start": [
        "¡Oki-doki, vamos al lío! ¡Intentemos no perder ningún dedo esta vez!",
        "¡Ay, cielos, hostiles a la vista! ¡Cúbrete, vamos al lío!",
        "¡Por el Refugio 33! ¡Oki-doki, vamos al lío en defensa propia!",
        "¡Madre mía, nos atacan! ¡Vamos al lío, yo te cubro!",
    ],
    "combat_end": [
        "¡Todo despachado! ¡Oki-doki, hemos salido de una pieza!",
        "¡Listo y todo despachado! Aunque voy a tener que lavar a fondo mi mono del Refugio 33.",
        "¡Amenaza neutralizada y todo despachado! Así se aplica la Regla de Oro... en defensa propia.",
        "¡Fiu, todo despachado! ¡Madre mía, qué buen equipo hacemos bajo presión!",
        "¡Todo despachado por aquí! ¡Oki-doki, ni un rasguño grave!",
    ],
    "companion_hurt": [
        "¡Ay, cielos, me han dado de lleno! ¡Necesito un estimulante!",
        "¡Madre mía, cómo duele esto! ¡Un poquito de ayuda médica, por favor!",
    ],
    "companion_recovered": [
        "¡Fiu, mucho mejor! ¡Oki-doki, ya estoy lista para volver al lío!",
    ],
    "affinity_like": [
        "¡Oki-doki! Eso ha estado genial, ¡así se hacen las cosas en un buen Refugio!",
        "¡Qué buena mano tienes! En el Refugio 33 estarían muy orgullosos de ti.",
        "¡Me gusta cómo trabajas, compañero! ¡Oki-doki, seguimos sumando puntos!",
        "¡Eso ha sido muy útil y constructivo! ¡Bien hecho!",
    ],
    "affinity_love": [
        "¡Madre mía, eso ha sido maravilloso! Viajar contigo me devuelve la fe en la superficie y en la Regla de Oro.",
        "¡Oki-doki, eso ha sido increíble! Eres exactamente el tipo de héroe que imaginaba cuando leía en el Refugio 33.",
        "¡Qué gesto tan noble! Te juro que viajar a tu lado es lo mejor que me ha pasado desde que salí de Santa Mónica.",
    ],
    "affinity_dislike": [
        "¡Ay, cielos! Eso no me ha gustado nada... va en contra de las normas de convivencia del Refugio 33.",
        "¡Oye! No deberíamos hacer ese tipo de cosas si queremos respetar la Regla de Oro.",
        "¡Madre mía! En el comité del Refugio 33 eso habría supuesto una amonestación grave.",
    ],
    "affinity_hate": [
        "¡Por todos los santos! ¡Eso ha sido cruel e innecesario! ¡No vine desde New Vegas para convertirme en alguien como El Necrófago!",
        "¡Basta! ¡Eso viola por completo la Regla de Oro! ¡No puedo aprobar que hagas daño a inocentes a sangre fría!",
    ],
    "affinity_max_perk": [
        "¡Oki-doki! Después de todo lo que sufrí con mi padre Hank y con Cooper, tú me has demostrado que la Regla de Oro sigue viva. ¡Cuenta conmigo para siempre, compañero del Refugio 111!",
    ],
}

_last_picked: dict[str, str] = {}


def is_bark_event(event_name: str) -> bool:
    return event_name in BARKS_ES


def pick_bark_text(event_name: str) -> str | None:
    options = BARKS_ES.get(event_name)
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
    h = hashlib.sha1(f"{voice_name}:es:{text}".encode("utf-8")).hexdigest()[:16]
    return BARKS_CACHE_DIR / f"{h}.wav"
