import ast
import csv
import pathlib

import orjson
import typer


app = typer.Typer()


@app.command("split-ce")
def split_common_events(ce_file: pathlib.Path, export_folder: pathlib.Path):
    common_events = orjson.loads(ce_file.read_bytes())
    for idx, ce in enumerate(common_events):
        if idx == 0:
            continue
        else:
            (
                export_folder / f"CommonEvents_Split_{str(idx).zfill(4)}.json"
            ).write_bytes(orjson.dumps([None, ce], option=orjson.OPT_INDENT_2))


@app.command("merge-ce")
def recombine_common_events(export_folder: pathlib.Path, new_ce):
    ce_files = [
        i
        for i in export_folder.iterdir()
        if i.is_file() and i.stem.startswith("CommonEvents_Split_")
    ]
    ce_files.sort(key=lambda file: int(file.stem.split("_")[-1]))
    print(ce_files)


@app.command()
def tpp_align(tpp_file: pathlib.Path):
    print("Reading trans file could take some time. Be patient...")
    trans = orjson.loads(tpp_file.read_bytes())
    dump_csvs = [
        i.name
        for i in pathlib.Path("outputs").iterdir()
        if ".json" == i.suffix and "_dump" in i.stem
    ]
    
    for file_k, file_data in trans["project"]["files"].items():
        rows = []
        expects = pathlib.Path(file_k).stem + "_dump.json"
        if expects in dump_csvs:
            json_dump = pathlib.Path("outputs") / expects
            json_data = orjson.loads(json_dump.read_bytes())
            print("Found", json_dump, "to be a valid json.")
            json_data = dict(
                (k, v) if isinstance(v, str) else (ast.literal_eval(k), v)
                for k, v in json_data.items()
            )
            for k, v in json_data.copy().items():
                if isinstance(v, list):
                    for idx, choices in enumerate(k):
                        json_data[choices] = v[idx]
            for k, v in json_data.copy().items():
                if isinstance(k,tuple):
                    json_data["".join(k)] = "".join(v)
            print(json_data)

            for row in file_data["data"]:
                if not row or row[0] is None:
                    rows.append([row[0], ""])
                elif row[0] in json_data:
                    rows.append([row[0], json_data[row[0]]])
                elif row[0].replace("\n","") in json_data:
                    rows.append([row[0], json_data[row[0].replace("\n","")]])
                else:
                    rows.append([row[0], ""])
            if rows:
                with open(
                    json_dump.with_stem(json_dump.stem + "_tppsv").with_suffix(".csv"),
                    "w",
                    newline="",
                    encoding="utf-8",
                ) as csvfp:
                    spamwriter = csv.writer(
                        csvfp, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL
                    )
                    spamwriter.writerows(rows)
    


if __name__ == "__main__":
    app()
