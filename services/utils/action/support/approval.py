from services.support.logger_util import _log as log

def wait_for_approval(batch_id: str, verbose: bool = False):
    log(f"Batch ID: {batch_id}", verbose, log_caller_file="approval.py")
    print(f"\nBatch ID: {batch_id}")
    print("Review and approve replies in your external system")
    print("Press Enter when ready to post approved replies...")

    input()
    log("User confirmed to proceed with posting", verbose, log_caller_file="approval.py")
