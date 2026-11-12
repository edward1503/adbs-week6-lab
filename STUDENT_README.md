# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

In this lab you look at how PostgreSQL chooses a plan for a query. Everything runs on your own laptop, with Docker.

## Before the lab: set up at home (about 20 minutes)

Please do this before Monday 30 November. The first start downloads about 1 GB, which is slow on the
classroom Wi-Fi. You need about 3 GB of free disk space.

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and keep the default options.
   - Windows: choose the AMD64 download, or ARM64 if your laptop has a Snapdragon processor.
   - Mac: choose the version for your chip (Apple or Intel).

   Open Docker Desktop. You can skip signing in. Wait until it shows "Engine running" in the bottom-left corner.
2. Unzip this folder.
3. Open a terminal in the folder:
   - Windows 11: right-click an empty spot in the folder and choose "Open in Terminal".
     On Windows 10, hold Shift, right-click, and choose "Open PowerShell window here".
   - Mac: open Terminal, type `cd ` (with a space), drag the folder into the window, and press Enter.
4. Start the lab:

   ```
   docker compose up -d --build
   ```

5. Open http://localhost:8888 in your browser. The lab notebook opens.
6. Click the first code cell and press Shift+Enter. It should print "1 check passed".
7. Take a screenshot and post it in the Week 6 setup thread on Canvas by Sunday 29 November.

Stuck? Post a screenshot of the error in the same thread, and we will help you before the lab.

## On the day

1. Open Docker Desktop and wait for "Engine running".
2. In a terminal in the lab folder, run `docker compose up -d`.
3. Open http://localhost:8888 and work through the notebook from top to bottom.

Your answers are saved in `answers.json` in the lab folder. That is the file you hand in.
When you are done, stop the lab with `docker compose stop`.

## If something goes wrong

| What you see | What to do |
|---|---|
| "Could not run the checks" | The database is not running. Open Docker Desktop, then run `docker compose up -d`. |
| "port is already allocated" | Another program is using port 8888, often another Jupyter. Close it and run `docker compose up -d` again. |
| Checks fail after an optional task changed the data | Reset the database: run `docker compose down -v`, then `docker compose up -d`. |
| The download stops partway | Run `docker compose up -d --build` again. It continues where it stopped. |
| The plan picture from `show_pev2` is blank | It needs internet. Use the text plan above it. |
