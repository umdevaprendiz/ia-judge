from abc import ABC, abstractmethod

from ..valores.faixa import Faixa
from ..valores.fracao import Fracao
from ..valores.pena import Pena


class EstrategiaQuantum(ABC):
    """Quanto uma única circunstância desfavorável (1ª fase) pesa na pena.

    Não há fração legal fixa para isso — a jurisprudência usa critérios distintos.
    O motor trata o critério como plugável e o expõe no relatório (nome da estratégia),
    em vez de escondê-lo dentro do cálculo.
    """

    nome: str

    @abstractmethod
    def incremento_por_circunstancia(self, faixa: Faixa) -> Pena:
        raise NotImplementedError


class FracaoDoIntervalo(EstrategiaQuantum):
    """Cada circunstância desfavorável vale uma fração do intervalo (máximo - mínimo da faixa)."""

    def __init__(self, fracao: Fracao = Fracao(1, 8)):
        self.fracao = fracao
        self.nome = f"fração do intervalo ({fracao})"

    def incremento_por_circunstancia(self, faixa: Faixa) -> Pena:
        intervalo_dias = faixa.maximo.dias - faixa.minimo.dias
        return Pena(self.fracao.aplicar(intervalo_dias))


class FracaoDoMinimo(EstrategiaQuantum):
    """Cada circunstância desfavorável vale uma fração da pena mínima da faixa."""

    def __init__(self, fracao: Fracao = Fracao(1, 6)):
        self.fracao = fracao
        self.nome = f"fração do mínimo ({fracao})"

    def incremento_por_circunstancia(self, faixa: Faixa) -> Pena:
        return Pena(self.fracao.aplicar(faixa.minimo.dias))
