from pathlib import Path

import cv2
import numpy as np


source = Path(r"C:\Users\aishi\Downloads\zip audit.mp4")
target = Path(r"C:\Users\aishi\AuditAI\scripts\artifacts\zip_audit_contact_sheet.jpg")
capture = cv2.VideoCapture(str(source))
seconds = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85]
tiles = []
for second in seconds:
    capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
    ok, frame = capture.read()
    if not ok:
        continue
    if second in {5, 10, 20, 25, 30, 35, 40, 50, 55, 60, 65, 70, 75}:
        cv2.imwrite(str(target.parent / f"zip_audit_{second:02d}s.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 94])
    frame = cv2.resize(frame, (480, 256))
    cv2.rectangle(frame, (0, 0), (120, 34), (0, 0, 0), -1)
    cv2.putText(frame, f"{second}s", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    tiles.append(frame)
capture.release()
while len(tiles) % 3:
    tiles.append(np.zeros_like(tiles[0]))
rows = [np.concatenate(tiles[index:index + 3], axis=1) for index in range(0, len(tiles), 3)]
cv2.imwrite(str(target), np.concatenate(rows, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 88])
print(target)
