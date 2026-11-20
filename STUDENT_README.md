# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

In this lab you look at how PostgreSQL chooses a plan for a query. There are two ways to run it. Pick one:

- **Docker** (below): everything runs on your own laptop. Works without internet on the day.
- **Google Colab** (further down): nothing to install, only a browser and a Google account.
  You need internet during the lab.

## Option 1: Docker

### Before the lab: set up at home (about 20 minutes)

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

### On the day

1. Open Docker Desktop and wait for "Engine running".
2. In a terminal in the lab folder, run `docker compose up -d`.
3. Open http://localhost:8888 and work through the notebook from top to bottom.

Your answers are saved in `answers.json` in the lab folder. That is the file you hand in.
When you are done, stop the lab with `docker compose stop`.

## Option 2: Google Colab (no Docker)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/edward1503/adbs-week6-lab/blob/main/notebooks/lab_colab.ipynb)

1. Click the button above and sign in with a Google account. If Colab warns that the notebook was not
   written by Google, choose "Run anyway".
   (Or go to https://colab.research.google.com, choose File, then Upload notebook, and pick
   `notebooks/lab_colab.ipynb` from this folder.)
2. Choose File, then "Save a copy in Drive", so that your work is kept in your own Google Drive.
3. Run the first code cell. It installs PostgreSQL on the Colab machine and loads the data, which takes
   about 2 minutes. It should end with "1 check passed".
4. Before the lab, do steps 1 to 3 once and post a screenshot in the Week 6 setup thread on Canvas by Sunday 29 November.

On the day, open the notebook in Colab again and run the first cell again: Colab gives you a fresh machine
each session. At the end, run the last cell of the notebook. It downloads `answers.json`, which is the file you hand in.

## If something goes wrong

| What you see | What to do |
|---|---|
| "Could not run the checks" (Docker) | The database is not running. Open Docker Desktop, then run `docker compose up -d`. |
| "Could not run the checks" (Colab) | Colab started a new session. Run the first code cell again. |
| "The setup did not finish" (Colab) | Usually a network hiccup. Run the first code cell again. |
| "port is already allocated" | Another program is using port 8888, often another Jupyter. Close it and run `docker compose up -d` again. |
| Checks fail after an extra task changed the data | Run `reset_database()` in a new cell. It takes a few seconds and keeps your answers. |
| The download stops partway | Run `docker compose up -d --build` again. It continues where it stopped. |
