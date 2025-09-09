"""
MCP DSSAT Server (prototype)
============================

This application exposes MCP‑compatible tools – **run_dssat_experiment**, **create_dssat_experiment** – that wraps the DSSAT command‑line executable.
The DSSAT installation path and the root data directory are fixed on the server; the caller only chooses which project folder to run and which experiment file inside that folder.

Endpoints
---------
* **GET /tools/list**
  Returns a list with the tool’s JSON‑Schema metadata so an MCP‑capable client
  (e.g. an LLM agent) can discover how to call it.

* **POST /tools/call/{tool_name}**
  Invokes the tool with the JSON body `{"args": {...}}` that conforms to the
  `input_schema` previously advertised.

Configuration constants
-----------------------
DSSAT_EXE   – absolute path to `dscsm048.exe` (or respective version)
DATA_ROOT   – absolute path to the DSSAT “Data” directory that contains project
              folders (each with experiment files).

Example
-------
```bash
POST /tools/call/run_dssat_experiment
{
  "args": {
    "folder": "Apple",
    "experiment_file": "SPPI0101.GGX"
  }
}
```

This will execute:
```bash
cd $DATA_ROOT/Apple
$DSSAT_EXE A SPPI0101.GGX
```
and the response will include the run’s **stdout**, **stderr**, **exit_code**
and (if present) the parsed **SUMMARY.OUT** KPIs.

Security / guardrails
---------------------
* Validates that `folder` is a sub‑directory of `DATA_ROOT` – no path traversal.
* Checks that `experiment_file` exists inside the chosen folder.
"""

import os, json, subprocess, io, zipfile, shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi_mcp import FastApiMCP
from auth0_utils import *
from mcp_tools_utils import *
from dotenv import dotenv_values
import boto3
from botocore.client import Config
from botocore.exceptions import (
    NoCredentialsError,
    EndpointConnectionError,
    ClientError,
    BotoCoreError,
)

# Load .env variables
try:
    config = dotenv_values(".env")
    ACCESS_KEY = config["ACCESS_KEY"]
    SECRET_KEY = config["SECRET_KEY"]
    S3_BUCKET = config["S3_BUCKET"]
    S3_REGION = config["S3_REGION"]
except Exception as e:
    print("Error in getting env info.")
    raise e

# ---------------------------------------------------------------------------
# Hard‑coded DSSAT installation (adjust to your server)
# ---------------------------------------------------------------------------
# DSSAT_EXE = Path("/app/dssat-csm-os-develop/build/bin/dscsm048")  # ← change as needed
# DATA_ROOT = Path("/app/dssat-csm-os-develop/build/bin")           # ← change as needed

DSSAT_EXE = Path("/home/christos/dssat-csm-os/build/bin/dscsm048")  # ← change as needed
DATA_ROOT = Path("/home/christos/dssat-csm-os/build/bin")           # ← change as needed

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI()

# # Enable CORS (Cross-Origin Resource Sharing) to allow requests from any domain.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

auth = VerifyToken()

@app.get("/tools/list", operation_id="list_tools")
def list_tools(token: str = Security(auth.verify)) -> List[Dict[str, Any]]:
    """Endpoint required by the MCP spec for tool discovery."""
    return TOOLS_SPEC


@app.post("/tools/call/upload_and_collect_output_files", operation_id="upload_and_collect_output_files")
def upload_and_collect_output_files(payload: Dict[str, Any], token: str = Security(auth.verify)) -> Dict[str, Any]:

    # Validate the payload against the RunArgs schema
    if "folder" in payload:
        args = UploadCollectOutputArgs(**payload)                     # plain
    elif "args" in payload:
        args = UploadCollectOutputArgs(**payload["args"])             # wrapped
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected keys: folder"
        )

    # Check if directory exists and create it if not
    work_dir = (DATA_ROOT / args.folder).resolve()

    # Change to the target directory
    try:
        os.chdir(work_dir)
        print(f"Changed directory to {work_dir}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{work_dir} not found")
    except OSError as exc:
        print(f"Error changing directory to {work_dir}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Create an S3 client
    try:
        s3 = boto3.client("s3",
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY,
                        region_name=S3_REGION,
                        endpoint_url=f"https://s3.{S3_REGION}.amazonaws.com",
                        config=Config(signature_version='s3v4'))
    except NoCredentialsError as e:
        raise RuntimeError("AWS credentials are missing or invalid.") from e
    except EndpointConnectionError as e:
        raise RuntimeError(f"Could not reach S3 endpoint: {e.endpoint_url}") from e
    except (BotoCoreError, Exception) as e:
        raise RuntimeError(f"Failed to create S3 client: {e}") from e
    
    # Create a ZIP file name based on the folder name
    key = f"{args.folder}.zip"

    try:
        # Build ZIP in memory and upload
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(work_dir):
                for name in files:
                    full = Path(root) / name
                    arcname = str(full.relative_to(work_dir))
                    zf.write(full, arcname=arcname)
        buf.seek(0)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ZIP file: {e}"
        )
    try:
        # Upload the ZIP to S3
        s3.upload_fileobj(buf, S3_BUCKET, key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 ClientError [{code}]: {msg}"
        )
    except (BotoCoreError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload ZIP to S3: {e}"
        )   

    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete directory '{work_dir}': {e.strerror or e}"
        ) from e

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key}
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 ClientError [{code}]: {msg}"
        )
    except (BotoCoreError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {e}"
        )
    
    # Create the result object
    try:
        result = UploadCollectOutputArgsResult(
            exit_code=status.HTTP_200_OK,
            s3_presigned_url=url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create result object: {e}"
        )

    return json.loads(result.model_dump_json())

@app.post("/tools/call/download_files_from_s3", operation_id="download_files_from_s3")
def download_files_from_s3(payload: Dict[str, Any], token: str = Security(auth.verify)) -> Dict[str, Any]:
    
    # Validate the payload against the RunArgs schema
    if "folder" in payload and "experiment_file" in payload and "files_names_list" in payload:
        args = DownloadS3Args(**payload)                     # plain
    elif "args" in payload:
        args = DownloadS3Args(**payload["args"])             # wrapped
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected keys: folder & experiment_file & files_names_list"
        )

    # Check if directory exists and create it if not
    work_dir = (DATA_ROOT / args.folder).resolve()

    # Don't allow path traversal outside DATA_ROOT
    if DATA_ROOT not in work_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid folder (outside DATA_ROOT)")

    # Create the directory if it does not exist
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create directory '{work_dir}': {e.strerror or e}"
        ) from e

    # Change to the target directory
    try:
        os.chdir(work_dir)
        print(f"Changed directory to {work_dir}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{work_dir} not found")
    except OSError as exc:
        print(f"Error changing directory to {work_dir}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Create an S3 client
    try:
        s3 = boto3.client("s3", aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
    except NoCredentialsError as e:
        raise RuntimeError("AWS credentials are missing or invalid.") from e
    except EndpointConnectionError as e:
        raise RuntimeError(f"Could not reach S3 endpoint: {e.endpoint_url}") from e
    except (BotoCoreError, Exception) as e:
        raise RuntimeError(f"Failed to create S3 client: {e}") from e
    
    # Download each file from the S3 bucket
    errors = {}
    for s3_file in args.files_names_list:
        # Download each file from the S3 bucket
        try:
            s3.download_file(S3_BUCKET, s3_file, f"./{s3_file}")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            errors[s3_file] = f"S3 ClientError [{code}]: {msg}"
        except (BotoCoreError, Exception) as e:
            errors[s3_file] = f"Unexpected error: {e}"
    
    # Check if any downloads failed
    if errors:
        # If using FastAPI, you could raise HTTPException(status_code=502, detail={"downloads_failed": errors})
        raise RuntimeError(f"One or more downloads failed: {errors}")
    
    # Check if experiment file exists
    exp_file = work_dir / args.experiment_file
    if not exp_file.is_file():
        raise HTTPException(status_code=400, detail="Experiment file not found")

    # Create the result object
    try:
        result = DownloadS3ArgsResult(
            exit_code=status.HTTP_200_OK,
            folder_name=args.folder,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create result object: {e}"
        )

    return json.loads(result.model_dump_json())

@app.post("/tools/call/run_dssat_experiment", operation_id="run_dssat_experiment")
def run_dssat_experiment(payload: Dict[str, Any], token: str = Security(auth.verify)) -> Dict[str, Any]:
    # Validate the payload against the RunArgs schema
    if "folder" in payload and "experiment_file" in payload:
        args = RunArgs(**payload)                     # plain
    elif "args" in payload:
        args = RunArgs(**payload["args"])             # wrapped
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected keys: folder & experiment_file"
        )

    # Check if path to directory is correct
    work_dir = (DATA_ROOT / args.folder).resolve()
    if not work_dir.is_dir() or DATA_ROOT not in work_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid folder")

    # Change to the target directory
    try:
        os.chdir(work_dir)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{work_dir} not found")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    exp_file = work_dir / args.experiment_file
    if not exp_file.is_file():
        raise HTTPException(status_code=400, detail="Experiment file not found")

    # Build DSSAT command: <exe> A <exp_file>
    cmd = [str(DSSAT_EXE), "A", args.experiment_file]
    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="DSSAT run timed out")

    result = RunResult(
        exit_code=proc.returncode,
        stdout=proc.stdout[-10000:],
        stderr=proc.stderr[-10000:],
        summary=_parse_summary(work_dir),
    )

    return json.loads(result.model_dump_json())

# ---------------------------------------------------------------------------
# Helper function for output
# ---------------------------------------------------------------------------
def _parse_summary(work_dir: Path) -> Optional[Dict[str, Any]]:
    """Parse the standard SUMMARY.OUT (very naïvely) to extract key metrics."""
    summary_file = work_dir / "SUMMARY.OUT"
    if not summary_file.is_file():
        return None

    kpis: List[Dict[str, Any]] = []
    with summary_file.open() as fh:
        for line in fh:
            if line.startswith("@") or not line.strip():
                continue
            # DSSAT columns are fixed‑width; we pull a few common ones.
            # Users can extend this parser as needed.
            try:
                exp_code = line[0:8].strip()
                tdate = line[19:25].strip()   # planting date
                yield_kg = float(line[65:72].strip())
                kpis.append({"expt": exp_code, "pl_date": tdate, "yield_kg_ha": yield_kg})
            except Exception:
                pass

    return {"n_treatments": len(kpis), "treatments": kpis}

# Add the MCP server to your FastAPI app
mcp = FastApiMCP(
    app,  
    name="DSSAT API MCP",  # Name for your MCP server
    description="MCP server for DSSAT"  # Description
)

# Mount the MCP server to your FastAPI app
mcp.mount()

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)