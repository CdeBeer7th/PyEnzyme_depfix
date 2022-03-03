"""
File: creator.py
Project: core
Author: Jan Range
License: BSD-2 clause
-----
Last Modified: Tuesday June 15th 2021 6:28:16 pm
Modified By: Jan Range (<jan.range@simtech.uni-stuttgart.de>)
-----
Copyright (c) 2021 Institute of Biochemistry and Technical Biochemistry Stuttgart
"""

from pydantic import BaseModel, PrivateAttr, validator
from typing import Optional
from enum import Enum
from abc import ABC, abstractmethod

from pyenzyme.enzymeml.core.ontology import SBOTerm


class AbstractSpeciesDataclass(BaseModel):
    """Abstract dataclass to describe an EnzymeML/SBML species."""

    name: str
    meta_id: Optional[str]
    id: Optional[str]
    vessel_id: str
    init_conc: Optional[float] = None
    constant: bool
    boundary: bool
    unit: Optional[str] = None
    ontology: SBOTerm
    _unit_id: Optional[str] = PrivateAttr(default=None)
    uri: Optional[str]
    creator_id: Optional[str]


class AbstractSpecies(ABC, AbstractSpeciesDataclass):
    """Due to inheritance and type-checking issues, the dataclass has to be mixed in."""

    # ! Validators
    @validator("id")
    def set_meta_id(cls, id: Optional[str], values: dict):
        """Sets the meta ID when an ID is provided"""

        if id:
            # Set Meta ID with ID
            values["meta_id"] = f"METAID_{id.upper()}"

        return id


class AbstractSpeciesFactory(ABC):
    """
    Factory that returns a specific species instance.
    """

    enzymeml_part: str

    @abstractmethod
    def get_species(self, **kwargs) -> AbstractSpecies:
        """Return a new species object"""
