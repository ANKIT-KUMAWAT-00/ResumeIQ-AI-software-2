from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.services.storage.service import delete_private

def test_local_private_file_deletion(tmp_path):
 p=tmp_path/'private.dat';p.write_bytes(b'sensitive');assert p.exists();delete_private(str(p));assert not p.exists()
