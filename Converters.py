import csv
import pathlib
from typing import Optional
import orjson
import typer


app = typer.Typer()


@app.command(name="dump2csv")
def dump2csv(name_dedup:bool=False, custom_dir:Optional[pathlib.Path]=None, drop_names:bool=True):
    directory = custom_dir if custom_dir else pathlib.Path("outputs")
    for file in directory.iterdir():
        name_sets = set()
        if file.stem.endswith("_dump"):
            with open(
                file.with_stem(file.stem + "_csv").with_suffix(".csv"),
                "w",
                newline="",
                encoding="utf-8",
            ) as csvfp:
                spamwriter = csv.writer(
                    csvfp, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL
                )
                
                for k, v in orjson.loads(file.read_bytes()).items():
                    
                    if isinstance(v, list):
                        if name_dedup:
                            new_v = [i for i in v if i not in name_sets]
                            name_sets.update(new_v)
                            v = new_v
                        v = "\n".join(v)
                        v= v.replace("\\n","\n")
                        spamwriter.writerow([k, v])
                    else:
                        v= v.replace("\\n","\n")
                        spamwriter.writerow([k, v])


@app.command(name="_")
def dummy():
    raise NotImplementedError("Dummy Command. Do not use.")


if __name__ == "__main__":
    app()
