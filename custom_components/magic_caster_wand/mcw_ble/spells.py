"""Spell definitions for Magic Caster Wand."""

from abc import ABC, abstractmethod

from .macros import LedGroup, Macro

class Spell(ABC):
    """Abstract base class for spell definitions."""

    Name: str

    @abstractmethod
    def payoff(self) -> Macro:
        """Return the macro to execute for this spell."""
        pass

class Aberto(Spell):
    Name = "aberto"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFDD66", 300)
            .add_delay(200)
            .add_clear())

class Accio(Spell):
    Name = "accio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "6688FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "4466DD", 250)
            .add_delay(200)
            .add_clear())

class Aguamenti(Spell):
    Name = "aguamenti"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "0066FF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "00AAFF", 300)
            .add_delay(200)
            .add_clear())

class Alohomora(Spell):
    Name = "alohomora"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFD700", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFAA00", 250)
            .add_delay(200)
            .add_clear())

class Anteoculatia(Spell):
    Name = "anteoculatia"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_led_hex(LedGroup.MID_UPPER, "A0522D", 250)
            .add_delay(200)
            .add_clear())

class AppareVestigium(Spell):
    Name = "appare_vestigium"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFDD00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFCC00", 300)
            .add_delay(300)
            .add_clear())

class AraniaExumai(Spell):
    Name = "arania_exumai"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF00", 150)
            .add_delay(150)
            .add_clear())

class Ascendio(Spell):
    Name = "ascendio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.POMMEL, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_LOWER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_UPPER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "AACCFF", 200)
            .add_delay(100)
            .add_clear())

class AvadaKedavra(Spell):
    Name = "avada_kedavra"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(500)
            .add_led_hex(LedGroup.TIP, "00FF00", 100)
            .add_led_hex(LedGroup.MID_UPPER, "00FF00", 100)
            .add_led_hex(LedGroup.MID_LOWER, "00FF00", 100)
            .add_led_hex(LedGroup.POMMEL, "00FF00", 100)
            .add_delay(200)
            .add_clear())

class Bombarda(Spell):
    Name = "bombarda"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(500)
            .add_led_hex(LedGroup.TIP, "FF4500", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FF4500", 120)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 100)
            .add_led_hex(LedGroup.POMMEL, "FF8800", 80)
            .add_delay(150)
            .add_clear())

class Brachiabindo(Spell):
    Name = "brachiabindo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "996633", 300)
            .add_delay(200)
            .add_clear())

class Calvorio(Spell):
    Name = "calvorio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFEECC", 200)
            .add_delay(150)
            .add_clear())

class Cantis(Spell):
    Name = "cantis"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFCC99", 250)
            .add_led_hex(LedGroup.MID_UPPER, "FFAA88", 20)
            .add_delay(200)
            .add_clear())

class Colloportus(Spell):
    Name = "colloportus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "886633", 300)
            .add_led_hex(LedGroup.MID_UPPER, "664422", 250)
            .add_delay(200)
            .add_clear())

class Colloshoo(Spell):
    Name = "colloshoo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AA8844", 300)
            .add_delay(200)
            .add_clear())

class Colovaria(Spell):
    Name = "colovaria"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "00FF00", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "0000FF", 200)
            .add_delay(100)
            .add_clear())

class Confringo(Spell):
    Name = "confringo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "FF0000", 100)
            .add_led_hex(LedGroup.MID_UPPER, "FF4500", 100)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 100)
            .add_led_hex(LedGroup.POMMEL, "FFFF00", 100)
            .add_delay(200)
            .add_clear())

class Confundo(Spell):
    Name = "confundo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFAAFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "AAFFFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 200)
            .add_delay(150)
            .add_clear())

class Densaugeo(Spell):
    Name = "densaugeo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFCC", 250)
            .add_delay(150)
            .add_clear())

class Depulso(Spell):
    Name = "depulso"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF8844", 250)
            .add_led_hex(LedGroup.MID_UPPER, "FF6622", 200)
            .add_delay(200)
            .add_clear())

class Descendo(Spell):
    Name = "descendo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_UPPER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.MID_LOWER, "88AAFF", 100)
            .add_delay(50)
            .add_led_hex(LedGroup.POMMEL, "6688DD", 200)
            .add_delay(100)
            .add_clear())

class Entomorphis(Spell):
    Name = "entomorphis"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "336633", 250)
            .add_delay(150)
            .add_clear())

class Evanesco(Spell):
    Name = "evanesco"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "888888", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "444444", 100)
            .add_delay(100)
            .add_clear())

class EverteStatum(Spell):
    Name = "everte_statum"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF6644", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF4422", 150)
            .add_delay(150)
            .add_clear())

class ExpectoPatronum(Spell):
    Name = "expecto_patronum"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "E0E0FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "C0C0FF", 300)
            .add_led_hex(LedGroup.MID_LOWER, "A0A0FF", 300)
            .add_led_hex(LedGroup.POMMEL, "8080FF", 300)
            .add_delay(500)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 1000)
            .add_delay(500)
            .add_clear())

class Expelliarmus(Spell):
    Name = "expelliarmus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF0000", 150)
            .add_led_hex(LedGroup.POMMEL, "FF0000", 100)
            .add_delay(300)
            .add_clear())

class Expulso(Spell):
    Name = "expulso"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(400)
            .add_led_hex(LedGroup.TIP, "FF6600", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFAA00", 200)
            .add_delay(150)
            .add_clear())

class Finestra(Spell):
    Name = "finestra"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 150)
            .add_led_hex(LedGroup.MID_UPPER, "CCCCFF", 100)
            .add_delay(100)
            .add_clear())

class Finite(Spell):
    Name = "finite"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AAAAFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "6666FF", 200)
            .add_delay(150)
            .add_clear())

class Flagrate(Spell):
    Name = "flagrate"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FF6600", 400)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 300)
            .add_delay(300)
            .add_led_hex(LedGroup.TIP, "FF9900", 300)
            .add_delay(200)
            .add_clear())

class Flipendo(Spell):
    Name = "flipendo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF6633", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF4422", 150)
            .add_delay(150)
            .add_clear())

class Fulgari(Spell):
    Name = "fulgari"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFFF00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF00", 250)
            .add_led_hex(LedGroup.MID_LOWER, "FFFF00", 200)
            .add_delay(300)
            .add_clear())

class Glacius(Spell):
    Name = "glacius"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "00FFFF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "88FFFF", 300)
            .add_led_hex(LedGroup.MID_LOWER, "AAFFFF", 250)
            .add_delay(300)
            .add_clear())

class Herbivicus(Spell):
    Name = "herbivicus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00AA00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "00DD00", 250)
            .add_led_hex(LedGroup.MID_LOWER, "00FF00", 200)
            .add_delay(250)
            .add_clear())

class Immobulus(Spell):
    Name = "immobulus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "88FFFF", 350)
            .add_led_hex(LedGroup.MID_UPPER, "66DDDD", 300)
            .add_delay(250)
            .add_clear())

class Impedimenta(Spell):
    Name = "impedimenta"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "8888FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "6666DD", 250)
            .add_delay(200)
            .add_clear())

class Incarcerous(Spell):
    Name = "incarcerous"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_led_hex(LedGroup.MID_UPPER, "A0522D", 250)
            .add_delay(200)
            .add_clear())

class Incendio(Spell):
    Name = "incendio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF4500", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 300)
            .add_delay(200)
            .add_clear())

class Langlock(Spell):
    Name = "langlock"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "AA6666", 250)
            .add_delay(150)
            .add_clear())

class Locomotor(Spell):
    Name = "locomotor"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "6699FF", 250)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "99AAFF", 250)
            .add_delay(150)
            .add_clear())

class Lumos(Spell):
    Name = "lumos"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led(LedGroup.TIP, 255, 255, 255, 2000))

class Melefors(Spell):
    Name = "melefors"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF8800", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 250)
            .add_delay(200)
            .add_clear())

class Meteolojinx(Spell):
    Name = "meteolojinx"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "666688", 300)
            .add_led_hex(LedGroup.MID_UPPER, "888899", 250)
            .add_delay(150)
            .add_led_hex(LedGroup.TIP, "FFFF00", 100)
            .add_delay(10)
            .add_clear())

class MucusAdNauseum(Spell):
    Name = "mucus_ad_nauseum"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "66FF66", 250)
            .add_delay(150)
            .add_clear())

class Nox(Spell):
    Name = "nox"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(100)
            .add_led_hex(LedGroup.TIP, "330033", 200)
            .add_delay(100)
            .add_clear())

class Orchideous(Spell):
    Name = "orchideous"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF66FF", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF99FF", 250)
            .add_delay(200)
            .add_clear())

class PestisIncendium(Spell):
    Name = "pestis_incendium"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF3300", 200)
            .add_led_hex(LedGroup.MID_LOWER, "FF6600", 200)
            .add_led_hex(LedGroup.POMMEL, "FF9900", 200)
            .add_delay(300)
            .add_clear())

class PetrificusTotalus(Spell):
    Name = "petrificus_totalus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "CCCCCC", 300)
            .add_led_hex(LedGroup.MID_UPPER, "AAAAAA", 250)
            .add_led_hex(LedGroup.MID_LOWER, "888888", 200)
            .add_delay(300)
            .add_clear())

class PiertotumLocomotor(Spell):
    Name = "piertotum_locomotor"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "CCCCCC", 250)
            .add_led_hex(LedGroup.MID_UPPER, "AAAAAA", 250)
            .add_led_hex(LedGroup.MID_LOWER, "888888", 200)
            .add_led_hex(LedGroup.POMMEL, "666666", 150)
            .add_delay(300)
            .add_clear())

class Protego(Spell):
    Name = "protego"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "0055FF", 500)
            .add_led_hex(LedGroup.MID_UPPER, "0055FF", 400)
            .add_led_hex(LedGroup.MID_LOWER, "0055FF", 300)
            .add_delay(300)
            .add_clear())

class Quietus(Spell):
    Name = "quietus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "666688", 250)
            .add_delay(150)
            .add_clear())

class Reducto(Spell):
    Name = "reducto"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "FF3300", 200)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "FFAA00", 150)
            .add_delay(100)
            .add_clear())

class Reparo(Spell):
    Name = "reparo"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFDD88", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFCC66", 250)
            .add_delay(200)
            .add_clear())

class Revelio(Spell):
    Name = "revelio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFFFF", 150)
            .add_led_hex(LedGroup.MID_UPPER, "FFFF88", 150)
            .add_led_hex(LedGroup.MID_LOWER, "FFFF00", 150)
            .add_delay(200)
            .add_clear())

class Rictusempra(Spell):
    Name = "rictusempra"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAACC", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FFCCDD", 200)
            .add_delay(150)
            .add_clear())

class Riddikulus(Spell):
    Name = "riddikulus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FFFF00", 200)
            .add_led_hex(LedGroup.MID_UPPER, "FF00FF", 200)
            .add_led_hex(LedGroup.MID_LOWER, "00FFFF", 200)
            .add_delay(200)
            .add_clear())

class SalvioHexia(Spell):
    Name = "salvio_hexia"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "6666FF", 400)
            .add_led_hex(LedGroup.MID_UPPER, "4444FF", 350)
            .add_led_hex(LedGroup.MID_LOWER, "2222FF", 300)
            .add_led_hex(LedGroup.POMMEL, "0000FF", 250)
            .add_delay(250)
            .add_clear())

class Scourgify(Spell):
    Name = "scourgify"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "88DDFF", 300)
            .add_delay(200)
            .add_clear())

class Silencio(Spell):
    Name = "silencio"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "9999AA", 300)
            .add_delay(200)
            .add_clear())

class Sonorus(Spell):
    Name = "sonorus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAA66", 250)
            .add_delay(150)
            .add_clear())

class SpellFail(Spell):
    Name = "spell_fail"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "000000", 100)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_delay(100)
            .add_clear())

class SpellSuccess(Spell):
    Name = "spell_success"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00FF00", 300)
            .add_delay(200)
            .add_clear())

class Spongify(Spell):
    Name = "spongify"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFCCFF", 300)
            .add_delay(200)
            .add_clear())

class Stupefy(Spell):
    Name = "stupefy"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "880000", 150)
            .add_delay(50)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(100)
            .add_clear())

class TheCheeringCharm(Spell):
    Name = "the_cheering_charm"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFFF00", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FFDD00", 250)
            .add_delay(200)
            .add_clear())

class TheForceSpell(Spell):
    Name = "the_force_spell"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(350)
            .add_led_hex(LedGroup.TIP, "88AAFF", 250)
            .add_led_hex(LedGroup.MID_UPPER, "6688DD", 200)
            .add_delay(200)
            .add_clear())

class TheHairThickeningGrowingCharm(Spell):
    Name = "the_hair_thickening_growing_charm"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "8B4513", 300)
            .add_delay(200)
            .add_clear())

class TheHourReversalCharm(Spell):
    Name = "the_hour_reversal_charm"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.TIP, "FFDD88", 200)
            .add_led_hex(LedGroup.MID_UPPER, "DDBB66", 200)
            .add_led_hex(LedGroup.MID_LOWER, "BB9944", 200)
            .add_led_hex(LedGroup.POMMEL, "997722", 200)
            .add_delay(250)
            .add_clear())

class TheHourReversalReversalCharm(Spell):
    Name = "the_hour_reversal_reversal_charm"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(300)
            .add_led_hex(LedGroup.POMMEL, "997722", 200)
            .add_led_hex(LedGroup.MID_LOWER, "BB9944", 200)
            .add_led_hex(LedGroup.MID_UPPER, "DDBB66", 200)
            .add_led_hex(LedGroup.TIP, "FFDD88", 200)
            .add_delay(250)
            .add_clear())

class ThePepperBreathHex(Spell):
    Name = "the_pepper_breath_hex"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(250)
            .add_led_hex(LedGroup.TIP, "FF4400", 300)
            .add_led_hex(LedGroup.MID_UPPER, "FF6600", 250)
            .add_delay(200)
            .add_clear())

class TheSleepingCharm(Spell):
    Name = "the_sleeping_charm"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "6666AA", 400)
            .add_delay(300)
            .add_clear())

class TheStretchingJinx(Spell):
    Name = "the_stretching_jinx"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FFAA88", 300)
            .add_delay(200)
            .add_clear())

class Ventus(Spell):
    Name = "ventus"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "88CCFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "AADDFF", 200)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "88CCFF", 200)
            .add_delay(100)
            .add_clear())

class Verdimillious(Spell):
    Name = "verdimillious"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "00FF00", 200)
            .add_led_hex(LedGroup.MID_UPPER, "00AA00", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "00FF00", 150)
            .add_delay(200)
            .add_clear())

class Vermillious(Spell):
    Name = "vermillious"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(200)
            .add_led_hex(LedGroup.TIP, "FF0000", 200)
            .add_led_hex(LedGroup.MID_UPPER, "AA0000", 150)
            .add_delay(100)
            .add_led_hex(LedGroup.TIP, "FF0000", 150)
            .add_delay(200)
            .add_clear())

class WingardiumLeviosa(Spell):
    Name = "wingardium_leviosa"

    def payoff(self) -> Macro:
        return (Macro()
            .add_buzz(150)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 300)
            .add_delay(200)
            .add_led_hex(LedGroup.TIP, "FFFF66", 300)
            .add_delay(200)
            .add_led_hex(LedGroup.TIP, "FFFFAA", 300)
            .add_delay(300)
            .add_clear())

# List of all spell classes in same order as SpellDetector.SPELL_NAMES
ALL_SPELLS = [
    TheForceSpell,
    Colloportus,
    Colloshoo,
    TheHourReversalReversalCharm,
    Evanesco,
    Herbivicus,
    Orchideous,
    Brachiabindo,
    Meteolojinx,
    Riddikulus,
    Silencio,
    Immobulus,
    Confringo,
    PetrificusTotalus,
    Flipendo,
    TheCheeringCharm,
    SalvioHexia,
    PestisIncendium,
    Alohomora,
    Protego,
    Langlock,
    MucusAdNauseum,
    Flagrate,
    Glacius,
    Finite,
    Anteoculatia,
    Expelliarmus,
    ExpectoPatronum,
    Descendo,
    Depulso,
    Reducto,
    Colovaria,
    Aberto,
    Confundo,
    Densaugeo,
    TheStretchingJinx,
    Entomorphis,
    TheHairThickeningGrowingCharm,
    Bombarda,
    Finestra,
    TheSleepingCharm,
    Rictusempra,
    PiertotumLocomotor,
    Expulso,
    Impedimenta,
    Ascendio,
    Incarcerous,
    Ventus,
    Revelio,
    Accio,
    Melefors,
    Scourgify,
    WingardiumLeviosa,
    Nox,
    Stupefy,
    Spongify,
    Lumos,
    AppareVestigium,
    Verdimillious,
    Fulgari,
    Reparo,
    Locomotor,
    Quietus,
    EverteStatum,
    Incendio,
    Aguamenti,
    Sonorus,
    Cantis,
    AraniaExumai,
    Calvorio,
    TheHourReversalCharm,
    Vermillious,
    ThePepperBreathHex,
]

# Dictionary mapping spell names to spell instances
SPELL_MAP = {spell.Name: spell() for spell in ALL_SPELLS}
