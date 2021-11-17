from enum import Enum


class SBOTerm(str, Enum):
    """String enumeration used to assign ontologies derived from SBOTerms."""

    # Chemical entities
    PROTEIN = "SBO:0000252"
    GENE = "SBO:0000251"
    SMALL_MOLECULE = "SBO:0000247"
    ION = "SBO:0000327"
    RADICAL = "SBO:0000328"

    # Chemical relations
    INTERACTOR = "SBO:0000336"
    SUBSTRATE = "SBO:0000015"
    PRODUCT = "SBO:0000011"
    CATALYST = "SBO:0000013"
    INHIBITOR = "SBO:0000020"
    ESSENTIAL_ACTIVATOR = "SBO:0000461"
    NON_ESSENTIAL_ACTIVATOR = "SBO:0000462"
    POTENTIATOR = "SBO:0000021"


class DataTypes(str, Enum):
    """String enumeration used to assign replicate type ontologies"""

    CONCENTRATION = "conc"
    ABSORPTION = "abs"
    FEED = "feed"
    BIOMASS = "biomass"
