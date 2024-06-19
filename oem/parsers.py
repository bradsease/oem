import re
from enum import Enum

from defusedxml.ElementTree import parse

Section = Enum("Section", ["HEADER", "META", "DATA", "COVARIANCE"])


HS = r"(?:[ \t]|$)+"
"""Arbitrary Horizontal spacing or EOL"""
KEY_VAL = f"([A-Z_]+){HS}={HS}(.+)"
"""Key-value pair"""

COV_XML_KEYS = (
    "CX_X",
    "CY_X",
    "CY_Y",
    "CZ_X",
    "CZ_Y",
    "CZ_Z",
    "CX_DOT_X",
    "CX_DOT_Y",
    "CX_DOT_Z",
    "CX_DOT_X_DOT",
    "CY_DOT_X",
    "CY_DOT_Y",
    "CY_DOT_Z",
    "CY_DOT_X_DOT",
    "CY_DOT_Y_DOT",
    "CZ_DOT_X",
    "CZ_DOT_Y",
    "CZ_DOT_Z",
    "CZ_DOT_X_DOT",
    "CZ_DOT_Y_DOT",
    "CZ_DOT_Z_DOT",
)


def err(line_number, message):
    raise ValueError(f"Error on line {line_number + 2}: {message}")


def parse_kvn_oem(ephem_file):
    section = Section.HEADER
    header, segments = {}, []
    covdata = None
    data_length = None

    match = re.match(KEY_VAL, ephem_file.readline())
    if match:
        header[match.group(1)] = match.group(2)
    if "CCSDS_OEM_VERS" not in header:
        err(line_number=0, message='OEM file must start with "CCSDS_OEM_VERS" keyword.')

    for idx, line in enumerate(ephem_file):
        line = line.strip()
        if line == "" or line.startswith("COMMENT"):
            continue  # TODO: Preserve comments

        elif section == Section.DATA:
            if line == "META_START":
                section = Section.META
                segments.append({"header": {}, "data": [], "cov": []})
                continue
            elif line == "COVARIANCE_START":
                section = Section.COVARIANCE
                continue

            date, *values = line.split()
            if data_length is None:
                data_length = len(values)
                if data_length not in (6, 9):
                    err(idx, "Malformed data entry")
            elif len(values) != data_length:
                err(idx, "Data contains mix of data lengths.")
            try:
                values = tuple(float(entry) for entry in values)
            except Exception:
                err(idx, "Malformed data entry")
            segments[-1]["data"].append((date, *values))

        elif section == Section.COVARIANCE:
            if line == "COVARIANCE_STOP":
                covdata = None
                continue
            elif line == "META_START":
                section = Section.META
                segments.append({"header": {}, "data": [], "cov": []})
                continue

            if not covdata:
                covdata = {
                    "frame": segments[-1]["header"]["REF_FRAME"],
                    "data": (),
                }
                in_header = True

            if "=" in line:
                if not in_header:
                    err(idx, "Malformed covariance")
                match = re.match(KEY_VAL, line)
                if match:
                    # TODO: Prevent repeats
                    if match.group(1) == "EPOCH":
                        covdata["epoch"] = match.group(2)
                    elif match.group(1) == "COV_REF_FRAME":
                        covdata["frame"] = match.group(2)
                    else:
                        err(idx, "Invalid covariance header")
                else:
                    err(idx, "Invalid covariance header")
            else:
                if in_header:
                    in_header = False
                    cov_data_line = 1
                    covdata["data"] = covdata["data"] + (float(line),)
                else:
                    cov_data_line += 1
                    raw_values = line.split()
                    if len(raw_values) != cov_data_line:
                        err(idx, "Malformed covariance shape")
                    try:
                        covdata["data"] = covdata["data"] + tuple(
                            float(entry) for entry in raw_values
                        )
                    except ValueError:
                        err(idx, "Malformed covariance data")

                    if cov_data_line == 6:
                        segments[-1]["cov"].append(
                            (
                                covdata["epoch"],
                                covdata["frame"],
                                *covdata["data"],
                            )
                        )
                        covdata = None

        elif section == Section.HEADER:
            if line == "META_START":
                section = Section.META
                segments.append({"header": {}, "data": [], "cov": []})
                continue

            match = re.match(KEY_VAL, line)
            if match:
                if match.group(1) in header:
                    err(idx, f"Duplicate header: {match.group(1)}")
                header[match.group(1)] = match.group(2)
            else:
                err(idx, "Invalid header entry")

        elif section == Section.META:
            if line == "META_STOP":
                section = Section.DATA
                data_length = None
                continue

            match = re.match(KEY_VAL, line)
            if match:
                if match.group(1) in segments[-1]["header"]:
                    err(idx, f"Duplicate entry: {match.group(1)}")
                segments[-1]["header"][match.group(1)] = match.group(2)
            else:
                err(idx, "Invalid meta entry")

    return header, segments


def parse_xml_oem(ephem_file):
    parts = parse(ephem_file).getroot()

    header = {
        entry.tag.rpartition("}")[-1]: entry.text
        for entry in parts[0]
        if entry.tag.rpartition("}")[-1] != "COMMENT"
    }
    header["CCSDS_OEM_VERS"] = parts.attrib["version"]

    segments = []
    for raw_segment in parts[1]:
        raw_metadata, raw_data = raw_segment

        segment = {}
        segment["header"] = {
            entry.tag.rpartition("}")[-1]: entry.text
            for entry in raw_metadata
            if entry.tag.rpartition("}")[-1] != "COMMENT"
        }

        keys = ("X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT")
        try:
            if raw_data.find("stateVector").find("X_DDOT") is not None:
                keys = keys + ("X_DDOT", "Y_DDOT", "Z_DDOT")
            segment["data"] = tuple(
                (entry.find("EPOCH").text,)
                + tuple(float(entry.find(key).text) for key in keys)
                for entry in raw_data
                if entry.tag.rpartition("}")[-1] == "stateVector"
            )
        except Exception:
            raise ValueError("Malformed data section")

        ref_frame = raw_metadata.find("REF_FRAME")
        try:
            segment["cov"] = tuple(
                (
                    entry.find("EPOCH").text,
                    (entry.find("COV_REF_FRAME") or ref_frame).text,
                    *(float(entry.find(key).text) for key in COV_XML_KEYS),
                )
                for entry in raw_data
                if entry.tag.rpartition("}")[-1] == "covarianceMatrix"
            )
        except Exception:
            raise ValueError("Malformed covariance section")

        segments.append(segment)

    return header, segments
