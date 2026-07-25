# OMM Specification Differences

This document compares only the Orbit Mean-Elements Message (OMM) requirements in
the CCSDS Orbit Data Message specifications. It does not summarize OPM, OEM, OCM,
or other message types.

## Specifications Compared

| Edition | Local specification | OMM coverage |
| --- | --- | --- |
| ODM 1.0, CCSDS 502.0-B-1 (September 2004) | `502x0b1s.pdf` | No OMM is defined. The document defines only OPM and OEM. |
| ODM 2.0, CCSDS 502.0-B-2 (November 2009, including Corr. 1) | `502x0b2s.pdf` | Introduces OMM version `2.0` in section 4. |
| ODM 3.0, CCSDS 502.0-B-3 (April 2023) | `502x0b3e2.pdf` | Defines OMM version `3.0` in section 4, KVN syntax in section 7, and XML construction in section 8.9. |

The separate `505x0b3e2.pdf` provides the common NDM/XML structure and schema
rules used by the OMM XML representation. The OMM-specific XML requirements are
in section 8.9 of `502x0b3e2.pdf`.

## Version History

### ODM 1.0 to ODM 2.0

ODM 1.0 contains no OMM. ODM 2.0 explicitly adds the OMM to support exchange of
mean-element orbit data and TLE-compatible data. This is stated in ODM 2.0
Annex E, item E1.1, and the new OMM is versioned with `CCSDS_OMM_VERS = 2.0`.

The v2 OMM consists of a header, metadata, data, and optional comments. Its data
has five logical blocks:

1. Mean Keplerian Elements
2. Spacecraft Parameters
3. TLE Related Parameters
4. Position/Velocity Covariance Matrix
5. User Defined Parameters

The v2 OMM establishes the core field set used by v3:

- Metadata: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`,
  `REF_FRAME_EPOCH`, `TIME_SYSTEM`, and `MEAN_ELEMENT_THEORY`.
- Mean elements: `EPOCH`, `SEMI_MAJOR_AXIS` or `MEAN_MOTION`, `ECCENTRICITY`,
  `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, and
  optional `GM`.
- Spacecraft parameters: `MASS`, `SOLAR_RAD_AREA`, `SOLAR_RAD_COEFF`,
  `DRAG_AREA`, and `DRAG_COEFF`.
- TLE parameters: `EPHEMERIS_TYPE`, `CLASSIFICATION_TYPE`, `NORAD_CAT_ID`,
  `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `BSTAR`, `MEAN_MOTION_DOT`, and
  `MEAN_MOTION_DDOT`.
- Optional 6x6 lower-triangular position/velocity covariance fields.
- Optional `USER_DEFINED_x` parameters, whose meanings must be documented in an
  ICD.

## ODM 2.0 to ODM 3.0

### Header

| Item | OMM 2.0 | OMM 3.0 |
| --- | --- | --- |
| Version | `CCSDS_OMM_VERS = 2.0` | `CCSDS_OMM_VERS = 3.0` |
| `COMMENT` | Optional; immediately after the version | Unchanged placement and status |
| `CLASSIFICATION` | Not defined | New optional free-text classification/caveats field |
| `CREATION_DATE` | Mandatory UTC time | Unchanged |
| `ORIGINATOR` | Mandatory; value coordinated in an ICD | Mandatory; selected from the SANA-registered originator set, with a procedure for adding an unlisted originator |
| `MESSAGE_ID` | Not defined | New optional identifier unique for a message from its originator |

`MESSAGE_ID` is explicitly identified as a v3 change in Annex J. `CLASSIFICATION`
is present as an optional OMM header field in the v3 table even though Annex J
does not call it out separately.

### Metadata

The metadata keyword names are unchanged, but several definitions become more
specific in v3.

| Keyword | OMM 2.0 | OMM 3.0 |
| --- | --- | --- |
| `OBJECT_NAME` | Recommended SPACEWARN naming | Recommended UN Office of Outer Space Affairs designator index naming; use `UNKNOWN` when the name is unknown or cannot be disclosed |
| `OBJECT_ID` | Recommended SPACEWARN international designator format | Recommended UN Office of Outer Space Affairs designator index format; use `UNKNOWN` when the identifier is unknown or cannot be disclosed |
| `CENTER_NAME` | Origin of the reference frame; no CCSDS restriction, with natural-body names recommended | Must be a natural solar-system body or an accepted natural-body barycenter; spacecraft centers are no longer described as valid OMM centers |
| `REF_FRAME` | Approved values are listed in the v2 annex; covariance may use a different frame | Values come from the v3 normative set. `TEME` is only for OMMs based on NORAD TLEs, and v3 prefers TEME of Date rather than TEME of Epoch |
| `REF_FRAME_EPOCH` | Optional | Conditional: required when the selected frame does not have an intrinsic epoch |
| `TIME_SYSTEM` | Mandatory; non-annex values require an ICD | Mandatory; non-normative values require an ICD, with the normative set maintained through the v3 SANA/annex material |
| `MEAN_ELEMENT_THEORY` | Examples include `SGP/SGP4`, `DSST`, and `USM` | Adds support for `SGP4-XP`; v3 also separates the `SGP` and `SGP4` model names in its examples and requirements |

### Data Fields and Conditions

The core mean-element, spacecraft-parameter, covariance, and user-defined field
names are retained. The significant v3 changes are in the TLE-related block.

| Change | OMM 2.0 | OMM 3.0 |
| --- | --- | --- |
| Drag-like ballistic coefficient | `BSTAR` for SGP/SGP4 use | `BSTAR` for SGP4, or new `BTERM` for SGP4-XP |
| Second mean-motion derivative / solar radiation parameter | `MEAN_MOTION_DDOT` | `MEAN_MOTION_DDOT` for SGP/PPT3, or new `AGOM` for SGP4-XP |
| First mean-motion derivative | Required for `SGP` | Conditional for `SGP` or `PPT3` |
| TLE model support | SGP/SGP4-oriented | Adds SGP4-XP and the associated BTERM/AGOM parameters |
| `EPHEMERIS_TYPE` coding guidance | Suggested codes included SGP, SGP4, SDP4, SGP8, and SDP8 | Updated suggested codes: `0 = SGP`, `2 = SGP4`, `3 = PPT3`, `4 = SGP4-XP`, and `6 = Special Perturbations` |

The `EPHEMERIS_TYPE` values are presented as suggested coding in both editions,
not as a new independent enumerated field. The v3 Annex J specifically identifies
the update to the numbering scheme and the pairing of `BSTAR`/`MEAN_MOTION_DDOT`
with `BTERM`/`AGOM`.

The following OMM data rules remain materially the same:

- Exactly one of `SEMI_MAJOR_AXIS` and `MEAN_MOTION` represents the size or mean
  motion of the orbit.
- `MEAN_MOTION` is required instead of `SEMI_MAJOR_AXIS` for TLE-based OMMs.
- All values describe the state at the `EPOCH`.
- Covariance is optional, but if supplied, all elements of the 6x6 lower triangle
  must be supplied. `COV_REF_FRAME` may be omitted when it equals `REF_FRAME`.
- User-defined parameters remain optional, non-standard, and subject to an ICD.
- Maneuvers are not represented in an OMM.

### KVN and XML Representation

OMM 2.0 defines OMM files as plain-text KVN messages. OMM 3.0 retains KVN and
continues to require fixed keyword ordering, a maximum line length of 254 ASCII
characters, optional units in square brackets, and comments only at the beginning
of the OMM logical blocks.

OMM 3.0 additionally specifies the XML representation directly:

- The root is `<omm ... id="CCSDS_OMM_VERS" version="3.0">`.
- The body contains exactly one `<segment>` with `<metadata>` followed by
  `<data>`.
- The OMM data blocks use `<meanElements>`, `<spacecraftParameters>`,
  `<tleParameters>`, `<covarianceMatrix>`, and `<userDefinedParameters>`.
- KVN keywords remain uppercase XML element names. Structural XML tags use
  lower camel case.
- `USER_DEFINED_x` KVN fields become `<USER_DEFINED parameter="x">value</USER_DEFINED>`
  elements inside `<userDefinedParameters>`.

The v3 syntax rules also clarify that comment and free-text values may use mixed
case, while normative text values remain all-uppercase or all-lowercase. This is
relevant to the new free-text `CLASSIFICATION` and `MESSAGE_ID` fields. The v3
time syntax retains the v2 formats and additionally calls out `60` seconds during
leap-second introduction.

The v3 document also notes that a sequence of OMMs for one or multiple objects
may be aggregated in a single NDM XML file. An individual OMM remains a
single-object message.

## Practical Compatibility Summary

| Consumer or producer | Compatibility implication |
| --- | --- |
| v1 implementation | Cannot process an OMM because OMM was not defined in ODM 1.0. |
| v2 implementation reading v3 | Must reject or ignore v3-only header fields and cannot interpret `BTERM`, `AGOM`, or the v3 SGP4-XP conventions as v2 OMM fields. It also cannot assume v3 metadata semantics. |
| v3 implementation reading v2 | Must accept the v2 field set and defaults, but a v2 message cannot provide v3-only `CLASSIFICATION`, `MESSAGE_ID`, `BTERM`, or `AGOM` information. |
| KVN parser | The overall OMM KVN structure is largely compatible, subject to the version value, changed field conditions, and v3 semantic restrictions. |
| XML parser | OMM 3.0 has an explicit `<omm>` XML structure and schema path; this is not an OMM format defined in the v1 document. |

## Source Locations

- ODM 1.0: `502x0b1s.pdf`, sections 1.1-1.4. It states that the standard defines
  only OPM and OEM.
- ODM 2.0: `502x0b2s.pdf`, sections 4.1-4.2 and Annex E item E1.1.
- ODM 2.0 syntax: `502x0b2s.pdf`, sections 6.3-6.7.
- ODM 3.0: `502x0b3e2.pdf`, sections 4.1-4.2 and Annex J items 2-4.
- ODM 3.0 syntax and XML: `502x0b3e2.pdf`, sections 7.3-7.10 and 8.9.
- Common OMM XML structure and user-defined parameter mapping:
  `505x0b3e2.pdf`, sections 3.2-3.6 and 4.10.
