# Learning router and metric constants

- **Unique ID:** FN-APP-LEARNING-PY-005
- **Source:** app/learning.py:1-20
- **Status:** VERIFIED — SOURCE RETRIEVED

## Behavior
Module imports the HTTP/database/cryptographic dependencies used by analytics ingestion, constructs an APIRouter mounted at `/learning-loop`, and declares the four metric names requested from Pinterest: IMPRESSION, SAVE, PIN_CLICK and OUTBOUND_CLICK.

## Implications
The router declaration itself performs no API call. The metric names form the external request contract used by run_learning_loop; their spelling and availability must be checked against the Pinterest API version used by the deployment. Importing this module also imports dependencies and application settings.

## Evidence boundary
Source retrieved from app/learning.py. No live API call or database write was performed.
