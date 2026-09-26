from enum import Enum


class Assessment(Enum):
    """Como uma circunstância pesa no caso: favorece o réu, é neutra, ou desfavorece."""

    FAVORAVEL = "favoravel"
    NEUTRA = "neutra"
    DESFAVORAVEL = "desfavoravel"


class JudicialCircumstance(Enum):
    """As 8 circunstâncias do art. 59 do CP, avaliadas na 1ª fase (pena-base)."""

    CULPABILIDADE = "culpabilidade"
    ANTECEDENTES = "antecedentes"
    CONDUTA_SOCIAL = "conduta_social"
    PERSONALIDADE = "personalidade"
    MOTIVOS = "motivos"
    CIRCUNSTANCIAS = "circunstancias"
    CONSEQUENCIAS = "consequencias"
    COMPORTAMENTO_DA_VITIMA = "comportamento_da_vitima"
