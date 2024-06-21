import re
import sys
from csv import DictWriter
from pathlib import Path
from traceback import print_exc
from typing import Any, Dict, Generator, List, Mapping, Union

from fhir_converter import renderers, utils
from jsonpath_ng.ext import parser
from liquid import FileExtensionLoader

a1c_regex = re.compile(r"a1c", re.IGNORECASE)
bp_regex = re.compile(r"diastolic|systolic|bp|blood pressure", re.IGNORECASE)

codified_path = parser.parse(
    "$[?(@.code.coding[?(@.system='http://loinc.org'&@.code!='')])]"
)
lab_path = parser.parse(
    "$.entry[?(@.resource.category[?(@.coding[?(@.code='laboratory')])])].resource"
)
vital_path = parser.parse(
    "$.entry[?(@.resource.category[?(@.coding[?(@.code='vital-signs')])])].resource"
)


def main(args: List[str]) -> None:
    if len(args) != 4:
        print("python inspector.py template template_dir ccda_dir data_out_dir")
        return
    templates_dir, data_in_dir, data_out_dir = list(map(Path, args[1:]))

    utils.mkdir(data_out_dir)
    with open(data_out_dir.joinpath("results.csv"), "w") as out_writer:
        renderer = renderers.CcdaRenderer(
            env=renderers.make_environment(
                loader=FileExtensionLoader(search_path=templates_dir),
                additional_loaders=[renderers.ccda_default_loader],
            )
        )
        writer = DictWriter(
            out_writer,
            fieldnames=["Filename", "labs", "vitals", "labs_w_loinc", "vitals_w_loinc"],
        )
        writer.writeheader()

        template_name, totals = args[0], {
            "labs": 0,
            "vitals": 0,
            "labs_w_loinc": 0,
            "vitals_w_loinc": 0,
        }
        for ccda_file in cda_files(data_in_dir):
            file_counts: Dict[str, Union[str, int]] = {
                "Filename": ccda_file.name,
                "labs": -1,
                "vitals": -1,
                "labs_w_loinc": -1,
                "vitals_w_loinc": -1,
            }
            try:
                with ccda_file.open(encoding="utf-8") as xml_in:
                    fhir_data = renderer.render_to_fhir(
                        template_name, xml_in, encoding="utf-8"
                    )

                    file_counts["labs"], file_counts["labs_w_loinc"] = count(
                        path=lab_path, json_data=fhir_data
                    )
                    file_counts["vitals"], file_counts["vitals_w_loinc"] = count(
                        path=vital_path, json_data=fhir_data
                    )

                    totals["labs"] += int(file_counts["labs"])
                    totals["vitals"] += int(file_counts["vitals"])
                    totals["labs_w_loinc"] += int(file_counts["labs_w_loinc"])
                    totals["vitals_w_loinc"] += int(file_counts["vitals_w_loinc"])
            except Exception:
                print_exc()
            writer.writerow(file_counts)
        writer.writerow(
            {
                "Filename": "Total",
                "labs": totals["labs"],
                "vitals": totals["vitals"],
                "labs_w_loinc": totals["labs_w_loinc"],
                "vitals_w_loinc": totals["vitals_w_loinc"],
            }
        )


def cda_files(from_dir: Path) -> Generator[Path, Any, None]:
    for root, _, filenames in utils.walk_path(from_dir):
        for file in filter(lambda p: p.suffix in (".ccda", ".xml"), map(Path, filenames)):
            yield root.joinpath(file)


def count(path, json_data: Mapping) -> tuple[int, int]:
    entries = path.find(json_data)
    return len(entries), len(codified_path.find(entries))


if __name__ == "__main__":
    main(sys.argv[1:])
