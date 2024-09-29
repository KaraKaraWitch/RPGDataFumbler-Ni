import csv
import pathlib
import orjson
import typer


app = typer.Typer()


@app.command(name="dump2csv")
def dump2csv():
    for file in pathlib.Path("outputs").iterdir():
        if file.stem.endswith("_dump"):
            with open(file.with_stem(file.stem + "_csv").with_suffix(".csv"),"w",newline="",encoding="utf-8") as csvfp:
                spamwriter = csv.writer(csvfp, delimiter='\t',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for k,v in orjson.loads(file.read_bytes()).items():
                    spamwriter.writerow([k,v])
            
        


@app.command(name="_")
def dummy():
    raise NotImplementedError("Dummy Command. Do not use.")


if __name__ == "__main__":
    app()
