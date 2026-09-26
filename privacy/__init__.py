"""Proteção de dados pessoais nas descrições de casos (LGPD)."""

from .anonimizacao import AnonymizationResult, Replacement, anonimizar

__all__ = ["AnonymizationResult", "Replacement", "anonimizar"]
