"""OMM KVN and XML parsing."""

from typing import Dict, TextIO, Tuple
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import parse as parse_xml

from .fields import HEADER_FIELDS, METADATA_FIELDS


def _local_name(element: Element) -> str:
    return element.tag.rpartition("}")[-1]


def _xml_fields(parent: Element) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for child in parent:
        key = _local_name(child)
        if key == "COMMENT":
            continue
        if key in fields:
            raise ValueError(f"Duplicate OMM XML field: {key}")
        fields[key] = (child.text or "").strip()
    return fields


def _add_fields(target: Dict[str, str], fields: Dict[str, str]) -> None:
    duplicate = next((key for key in fields if key in target), None)
    if duplicate:
        raise ValueError(f"Duplicate OMM field: {duplicate}")
    target.update(fields)


def _parse_xml_user_defined(parent: Element) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for child in parent:
        if _local_name(child) != "USER_DEFINED":
            raise ValueError("Invalid OMM XML user-defined parameter")
        parameter = child.attrib.get("parameter", "")
        if not parameter:
            raise ValueError("OMM XML user-defined parameter is missing its name")
        _add_fields(fields, {f"USER_DEFINED_{parameter}": (child.text or "").strip()})
    return fields


def _parse_kvn(
    file_obj: TextIO,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    sections: Dict[str, Dict[str, str]] = {"header": {}, "metadata": {}, "data": {}}
    phase = "header"
    for number, raw_line in enumerate(file_obj, start=1):
        line = raw_line.strip()
        if not line or line.startswith("COMMENT"):
            continue
        if line.endswith("_START") or line.endswith("_STOP"):
            raise ValueError(f"Invalid OMM delimiter on line {number}: {line}")
        if "=" not in line:
            raise ValueError(f"Invalid OMM entry on line {number}")
        key, value = (entry.strip() for entry in line.split("=", 1))
        if not key or (not value and key not in ("CREATION_DATE", "ORIGINATOR")):
            raise ValueError(f"Invalid OMM entry on line {number}")
        if key in HEADER_FIELDS:
            if phase != "header":
                raise ValueError(f"Header field after OMM data on line {number}")
            target = sections["header"]
        elif key in METADATA_FIELDS:
            if phase == "data":
                raise ValueError(f"Metadata field after OMM data on line {number}")
            phase = "metadata"
            target = sections["metadata"]
        else:
            phase = "data"
            target = sections["data"]
        _add_fields(target, {key: value})
    return sections["header"], sections["metadata"], sections["data"]


def _parse_xml(
    file_obj: TextIO,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    root = parse_xml(file_obj).getroot()
    if _local_name(root) != "omm":
        raise ValueError("XML document is not an OMM")
    header_element = next(
        (child for child in root if _local_name(child) == "header"), None
    )
    body_element = next((child for child in root if _local_name(child) == "body"), None)
    if header_element is None or body_element is None:
        raise ValueError("OMM XML must contain header and body elements")
    segments = [child for child in body_element if _local_name(child) == "segment"]
    if len(segments) != 1:
        raise ValueError("OMM XML must contain exactly one segment")
    metadata_element = next(
        (child for child in segments[0] if _local_name(child) == "metadata"), None
    )
    data_element = next(
        (child for child in segments[0] if _local_name(child) == "data"), None
    )
    if metadata_element is None or data_element is None:
        raise ValueError("OMM XML segment must contain metadata and data")

    header = _xml_fields(header_element)
    _add_fields(header, {"CCSDS_OMM_VERS": root.attrib.get("version", "")})
    data: Dict[str, str] = {}
    expected_sections = {
        "meanElements",
        "spacecraftParameters",
        "tleParameters",
        "covarianceMatrix",
        "userDefinedParameters",
    }
    for child in data_element:
        name = _local_name(child)
        if name == "COMMENT":
            continue
        if name not in expected_sections:
            raise ValueError(f"Invalid OMM XML data section: {name}")
        fields = (
            _parse_xml_user_defined(child)
            if name == "userDefinedParameters"
            else _xml_fields(child)
        )
        _add_fields(data, fields)
    return header, _xml_fields(metadata_element), data
