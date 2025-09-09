import json, ast
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
# ---------------------------------------------------------------------------
# Pydantic schemas for MCP
# ---------------------------------------------------------------------------
class RunArgs(BaseModel):
    """Arguments expected from the MCP client."""
    folder: str = Field(
        ...,
        description="Name of the sub‑directory under DATA_ROOT that contains the experiment. The name of the sub‑directory is the capitalized form of the crop. For example apple is Apple, APPLE is Apple",
        examples=["Apple"],
    )
    experiment_file: str = Field(
        ...,
        description="DSSAT FileX experiment file to run, filename ends with X.",
        examples=["SPPI0101.GGX"],
    )

class RunResult(BaseModel):
    """Returned to the client after the run is finished."""
    exit_code: int
    stdout: str
    stderr: str
    summary: Optional[Dict[str, Any]] = None  # parsed KPIs from SUMMARY.OUT

class DownloadS3Args(BaseModel):
    """Arguments expected from the MCP client."""
    folder: str = Field(
        ...,
        description="Name of the sub‑directory under DATA_ROOT that contains the experiment. The name of the sub‑directory is the capitalized form of the crop. For example apple is Apple, APPLE is Apple",
        examples=["Apple"],
    )
    experiment_file: str = Field(
        ...,
        description="DSSAT FileX experiment file to run, filename ends with X.",
        examples=["SPPI0101.GGX"],
    )
    files_names_list: List[str] = Field(
        ...,
        description="List of DSSAT experiment files",
        examples=["SOIL.SOL", "UFGA8201.WTH", "UFGA8201.MZX"],
    )

    @field_validator("files_names_list", mode="before")
    def coerce_files(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                x = json.loads(v)
            except json.JSONDecodeError:
                x = ast.literal_eval(v)
            if isinstance(x, list):
                return [str(i) for i in x]
        raise TypeError("files_names_list must be a list of strings")

class DownloadS3ArgsResult(BaseModel):
    """Returned to the client after the run is finished."""
    exit_code: int
    folder_name: str

class UploadCollectOutputArgs(BaseModel):
    """Arguments expected from the MCP client."""
    folder: str = Field(
        ...,
        description="Name of the sub‑directory under DATA_ROOT that contains the experiment. The name of the sub‑directory is the capitalized form of the crop. For example apple is Apple, APPLE is Apple",
        examples=["Apple"],
    )

class UploadCollectOutputArgsResult(BaseModel):
    """Returned to the client after the run is finished."""
    exit_code: int
    s3_presigned_url: str

# JSON Schema used in /tools/list
RUN_INPUT_SCHEMA = RunArgs.model_json_schema()
RUN_OUTPUT_SCHEMA = RunResult.model_json_schema()
S3_INPUT_SCHEMA = DownloadS3Args.model_json_schema()
S3_OUTPUT_SCHEMA = DownloadS3ArgsResult.model_json_schema()
UPL_COL_INPUT_SCHEMA = UploadCollectOutputArgs.model_json_schema()
UPL_COL_OUTPUT_SCHEMA = UploadCollectOutputArgsResult.model_json_schema()

TOOLS_SPEC = [{
    "name": "run_dssat_experiment",
    "description": (
        "Run a DSSAT experiment with the file specified by the user, which always ends with the letter X. It is located in a sub‑directory with the capitalized name of the crop specified by the user.\n"
        "Required arguments:\n"
        "1) folder – DSSAT project sub-directory under DATA_ROOT (e.g. 'Apple').\n"
        "2) experiment_file – FileX filename ending with X (e.g. 'SPPI0101.GGX')."
    ),
    "input_schema": RUN_INPUT_SCHEMA,
    "output_schema": RUN_OUTPUT_SCHEMA,
    "examples": [
        {
            "comment": "Brachiaria example – single FileX",
            "args": {"folder": "Brachiaria", "experiment_file": "CNCH8201.BRX"}
        },
        {
            "comment": "Wheat example – single FileX",
            "args": {"folder": "Wheat", "experiment_file": "SWSW7501.WHX"}
        },
        {
            "comment": "Unspecified crop – single FileX",
            "args": {"folder": "Custom_Folder_Name", "experiment_file": "Custom_Experiment_File.X"}
        },        
    ],
},
{
    "name": "download_files_from_s3",
    "description": (
        "Download files from S3 for a DSSAT experiment with the file names specified by the user. The user provides a multiple file names which must be parsed as a list of strings. The user specifies which is the experiment file, which always ends with the letter X.\n"
        "Required arguments:\n"
        "1) folder – DSSAT project sub-directory under DATA_ROOT (e.g. 'Apple').\n"
        "2) experiment_file – FileX filename ending with X (e.g. 'SPPI0101.GGX').\n"
        "3) files_names_list – List of strings with the names of the files to run (e.g. ['SOIL.SOL', 'UFGA8201.WTH', 'UFGA8201.MZX'])."
    ),
    "input_schema": S3_INPUT_SCHEMA,
    "output_schema": S3_OUTPUT_SCHEMA,
    "examples": [
        {
            "comment": "Brachiaria example – single FileX",
            "args": {"folder": "Brachiaria", "experiment_file": "CNCH8201.BRX", "files_names_list": ["SOIL.SOL", "CNCH8201.WTH", "CNCH8201.MZX"]}
        },
        {
            "comment": "Wheat example – single FileX",
            "args": {"folder": "Wheat", "experiment_file": "SWSW7501.WHX", "files_names_list": ["SOIL.SOL", "SWSW7501.WTH", "SWSW7501.MZX"]}
        },
        {
            "comment": "Unspecified crop – single FileX",
            "args": {"folder": "Custom_Folder_Name", "experiment_file": "Custom_Experiment_File.X", "files_names_list": ["Custom_File1.SOL", "Custom_File2.WTH", "Custom_File3.MZX"]}
        },
    ],
},
{
    "name": "upload_and_collect_output_files",
    "description": (
        "Upload zipped output folder to S3 from a DSSAT experiment. The name is provided by the user. Then return a presigned S3 url for the user to download the zip file.\n"
        "Required arguments:\n"
        "1) folder – DSSAT project sub-directory under DATA_ROOT (e.g. 'Apple').\n"
    ),
    "input_schema": UPL_COL_INPUT_SCHEMA,
    "output_schema": UPL_COL_OUTPUT_SCHEMA,
    "examples": [
        {
            "comment": "Brachiaria example – single FileX",
            "args": {"folder": "Brachiaria"}
        },
        {
            "comment": "Wheat example – single FileX",
            "args": {"folder": "Wheat"}
        },
        {
            "comment": "Unspecified crop – single FileX",
            "args": {"folder": "Custom_Folder_Name"}
        },
    ],
}
]
