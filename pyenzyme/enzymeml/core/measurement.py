'''
File: measurement.py
Project: core
Author: Jan Range
License: BSD-2 clause
-----
Last Modified: Thursday July 15th 2021 1:19:51 am
Modified By: Jan Range (<jan.range@simtech.uni-stuttgart.de>)
-----
Copyright (c) 2021 Institute of Biochemistry and Technical Biochemistry Stuttgart
'''

import pandas as pd

from typing import Optional, TYPE_CHECKING, Union
from dataclasses import dataclass
from pydantic import PositiveFloat, validate_arguments, Field, PrivateAttr

from pyenzyme.enzymeml.core.enzymemlbase import EnzymeMLBase
from pyenzyme.enzymeml.core.measurementData import MeasurementData
from pyenzyme.enzymeml.core.replicate import Replicate
from pyenzyme.enzymeml.core.exceptions import SpeciesNotFoundError
from pyenzyme.enzymeml.core.utils import (
    type_checking,
    deprecated_getter
)

if TYPE_CHECKING:  # pragma: no cover
    static_check_init_args = dataclass
else:
    static_check_init_args = type_checking


@static_check_init_args
class Measurement(EnzymeMLBase):

    name: str = Field(
        ...,
        description="Name of the measurement",
    )

    species_dict: dict[str, dict[str, MeasurementData]] = Field(
        {"proteins": {}, "reactants": {}},
        description="Species of the measurement.",
    )

    global_time: list[float] = Field(
        default_factory=list,
        description="Global time of the measurement all replicates agree on.",
    )

    global_time_unit: Optional[str] = Field(
        None,
        description="Unit of the global time.",
    )

    id: Optional[str] = Field(
        None,
        description="Unique identifier of the measurement.",
        regex=r"m[\d]+"
    )

    uri: Optional[str] = Field(
        None,
        description="URI of the reaction.",
    )

    creator_id: Optional[str] = Field(
        None,
        description="Unique identifier of the author.",
    )

    _global_time_unit_id: str = PrivateAttr(None)

    # ! Utility methods
    def exportData(self, species_ids: Union[str, list[str]] = "all") -> dict[str, dict[str, Union[dict[str, tuple[float, str]], pd.DataFrame]]]:
        """Returns data stored in the measurement object as DataFrames nested in dictionaries. These are sorted hierarchially by reactions where each holds a DataFrame each for proteins and reactants.

        Returns:
            measurements (dict): Follows the hierarchy Reactions > Proteins/Reactants > { initial_concentration, data }
            species_ids (Union[str, list[str]]): List of species IDs to extract data from. Defaults to 'all'.
        """

        # Combine Replicate objects for each reaction
        proteins = self._combineReplicates(
            measurement_species=self.species_dict['proteins'],
            species_ids=species_ids
        )
        reactants = self._combineReplicates(
            measurement_species=self.species_dict['reactants'],
            species_ids=species_ids
        )

        return {
            "proteins": proteins,
            "reactants": reactants
        }

    def _combineReplicates(
        self,
        measurement_species: dict[str, MeasurementData],
        species_ids: Union[str, list[str]] = "all"
    ) -> dict[str, Union[dict[str, tuple[float, str]], pd.DataFrame]]:
        """Combines replicates of a certain species to a dataframe.

        Args:
            measurement_species (dict[str, MeasurementData]): The species_dict from the measurement.

        Returns:
            dict[str, Any]: The associated replicat and initconc data.
        """

        if isinstance(species_ids, str):
            species_ids = [species_ids]

        columns = {f"time/{self.global_time_unit}": self.global_time}
        initial_concentration = {}

        # Iterate over measurementData to fill columns
        for species_id, data in measurement_species.items():

            if species_id in species_ids or species_ids == ["all"]:

                # Fetch replicate data
                for replicate in data.getReplicates():

                    header = f"{replicate.getReplica()}/{species_id}/{replicate.getDataUnit()}"
                    columns[header] = replicate.data

                    # Fetch initial concentration
                    initial_concentration[species_id] = (
                        data.init_conc, data._unit_id
                    )

        return {
            "data": pd.DataFrame(columns)
            if len(columns) > 1
            else pd.DataFrame(),
            "initConc": initial_concentration,
        }

    @validate_arguments
    def addReplicates(self, replicates: Union[list[Replicate], Replicate]) -> None:
        """Adds a replicate to the corresponding measurementData object. This method is meant to be called if the measurement metadata of a reaction/species has already been done and replicate data has to be added afterwards. If not, use addData instead to introduce the species metadata.

        Args:
            replicate (List<Replicate>): Objects describing time course data
        """

        # Check if just a single Replicate has been handed
        if isinstance(replicates, Replicate):
            replicates = [replicates]

        for replicate in replicates:

            # Check for the species type
            species_id = replicate.reactant_id
            speciesType = "reactants" if species_id[0] == "s" else "proteins"
            speciesData = self.species_dict[speciesType]

            try:

                data = speciesData[species_id]
                data.addReplicate(replicate)

                if len(self.global_time) == 0:

                    # Add global time if this is the first replicate to be added
                    self.global_time = replicate.getData(sep=True)[0]
                    self.global_time_unit = (replicate.getTimeUnit())

            except KeyError:
                raise KeyError(
                    f"{speciesType[0:-1]} {species_id} is not part of the measurement yet. If a {speciesType[0:-1]} hasnt been yet defined in a measurement object, use the addData method to define metadata first-hand. You can add the replicates in the same function call then."
                )

    @validate_arguments
    def addData(
        self,
        init_conc: float,
        unit: str,
        reactant_id: Optional[str] = None,
        protein_id: Optional[str] = None,
        replicates: list[Replicate] = []
    ) -> None:
        """Adds data to the measurement object.

        Args:
            init_conc (PositiveFloat): Corresponding initial concentration of species.
            unit (str): The SI unit of the measurement.
            reactant_id (Optional[str], optional): Identifier of the reactant that was measured. Defaults to None.
            protein_id (Optional[str], optional): Identifier of the protein that was measured. Defaults to None.
            replicates (list[Replicate], optional): List of replicates that were measured. Defaults to [].
        """

        self._appendReactantData(
            reactant_id=reactant_id,
            protein_id=protein_id,
            init_conc=init_conc,
            unit=unit,
            replicates=replicates
        )

    def _appendReactantData(
        self,
        reactant_id: Optional[str],
        protein_id: Optional[str],
        init_conc: float,
        unit: str,
        replicates: list[Replicate]
    ) -> None:

        # Create measurement data class before sorting
        measData = MeasurementData(
            reactant_id=reactant_id,
            protein_id=protein_id,
            init_conc=init_conc,
            unit=unit,
            replicates=replicates
        )

        if reactant_id:
            self.species_dict['reactants'][reactant_id] = measData
        elif protein_id:
            self.species_dict['proteins'][protein_id] = measData
        else:
            raise ValueError(
                "Please enter a reactant or protein ID to add measurement data"
            )

    def updateReplicates(self, replicates: list[Replicate]) -> None:
        for replicate in replicates:
            # Set the measurement name for the replicate
            replicate.measurement_id = self.name

    def _setReplicateMeasIDs(self) -> None:
        """Sets the measurement IDs for the replicates."""
        for measData in self.species_dict['proteins'].values():
            measData.measurement_id = self.id

        for measData in self.species_dict['reactants'].values():
            measData.measurement_id = self.id

    def unifyUnits(self, kind: str, scale: int, enzmldoc) -> None:
        """Rescales all replicates and measurements to match the scale of a unit kind.

        Args:
            kind (str): The unit kind from which to rescale. Currently supported: 'mole', 'gram', 'litre'.
            scale (int): Decade scale to which the values will be rescaled.
            enzmldoc (EnzymeMLDocument): The EnzymeMLDocument to which the new unit will be added.
        """

        for measurement_data in {**self.getProteins(), **self.getReactants()}.values():
            measurement_data.unifyUnits(
                kind=kind, scale=scale, enzmldoc=enzmldoc
            )

    # ! Getters

    @ validate_arguments
    def getReactant(self, reactant_id: str) -> MeasurementData:
        """Returns a single MeasurementData object for the given reactant_id.

        Args:
            reactant_id (String): Unqiue identifier of the reactant

        Returns:
            MeasurementData: Object representing the data and initial concentration
        """
        return self._getSpecies(reactant_id)

    def getProtein(self, protein_id: str) -> MeasurementData:
        """Returns a single MeasurementData object for the given protein_id.

        Args:
            protein_id (String): Unqiue identifier of the protein

        Returns:
            MeasurementData: Object representing the data and initial concentration
        """
        return self._getSpecies(protein_id)

    def getReactants(self) -> dict[str, MeasurementData]:
        """Returns a list of all participating reactants in the measurement.

        Returns:
            list: List of MeasurementData objects representing data
        """
        return self.species_dict["reactants"]

    def getProteins(self) -> dict[str, MeasurementData]:
        """Returns a list of all participating proteins in the measurement.

        Returns:
            list: List of MeasurementData objects representing data
        """
        return self.species_dict["proteins"]

    @ validate_arguments
    def _getSpecies(self, species_id: str) -> MeasurementData:
        all_species = {
            **self.species_dict["proteins"],
            **self.species_dict["reactants"]
        }

        try:
            return all_species[species_id]
        except KeyError:
            raise SpeciesNotFoundError(
                species_id=species_id,
                enzymeml_part="Measurement"
            )

    @deprecated_getter("id")
    def getId(self):
        return self.id

    @deprecated_getter("global_time_unit")
    def getGlobalTimeUnit(self):
        return self.global_time_unit

    @deprecated_getter("global_time")
    def getGlobalTime(self):
        return self.global_time

    @deprecated_getter("name")
    def getName(self):
        return self.name

    @deprecated_getter("species_dict")
    def getSpeciesDict(self):
        return self.species_dict
