import os

from cosmos.api import Cosmos, py_call


def add_one(out_file):
    if os.path.exists(out_file):
        with open(out_file) as fp:
            i = int(fp.read())
    else:
        i = 0

    with open(out_file, "w") as fp:
        fp.write(str(i + 1))

    if i < 2:
        # fail the first 2 times
        raise


if __name__ == "__main__":
    cosmos = Cosmos("sqlite.db", default_drm="local",)
    cosmos.initdb()
    workflow = cosmos.start("reattempt", restart=True, skip_confirm=True)

    if os.path.exists("out.txt"):
        os.unlink("out.txt")

    t = workflow.add_task(func=add_one, params=dict(out_file="out.txt"), uid="my_task", max_attempts=3)

    workflow.make_output_dirs()
    workflow.run(cmd_wrapper=py_call)
