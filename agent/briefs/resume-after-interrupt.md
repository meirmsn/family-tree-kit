# Brief: resume after an interrupted run

1. Read the last entry of `research-log.md` and list `.backups/` (newest first).
2. Compare the files with the newest backup (`diff -r`) to see what the interrupted run changed.
3. If a file was left half-written (broken table, unterminated section), restore that one file from
   the backup and redo that step; otherwise keep the work.
4. Write a log line: "Resumed Pass <N> at <time>; steps 1–k were complete; continuing at k+1."
5. Continue the original task list from the first step not marked done. Same rules, same ID ranges.
