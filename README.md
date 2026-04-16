# JogAir 🏃‍♂️💨
**Smart jogging app add-on for healthier running in Danish Smart Cities.**

## Project Overview
Urban air pollution poses significant health risks for individuals engaging in outdoor physical activities like jogging. While Danish cities like Aarhus and Copenhagen actively monitor air pollution, this data is often presented in static dashboards and isn't connected to daily mobility behavior. 

**JogAir** explores an air quality add-on integrated into an existing fitness app (like Strava). By leveraging machine learning models on historical pollution, weather, and traffic data, this project aims to forecast hyper-local air quality and provide actionable, health-conscious route recommendations.

## Data Science Trajectory
This project follows the **Product Exploration** trajectory. The objective is to design and explore a data-driven product that integrates predictive models and visualizations into an interactive application, rather than producing a static analytical report.

## Repository Structure
* `data/`: Local storage for raw API dumps and processed data (Ignored by Git).
* `notebooks/`: Jupyter notebooks for Exploratory Data Analysis (EDA) and model testing.
* `src/collectors/`: Scripts to fetch data from Open-Meteo and DMI APIs.
* `src/pipeline/`: Machine learning models for historical analysis and daily predictions.
* `app/`: The Streamlit interactive dashboard prototype.

## Setup Instructions for Collaborators

### Prerequisites
- Python 3.9 or higher
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Flaviusben/jogair_project.git
   cd jogair_project
   ```

2. **Create a virtual environment:**
   ```bash
   # On Windows
   python -m venv .venv
   .venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Generate your own data:**
   - The `data/raw/` and `data/processed/` folders are not included in the repository (Git-ignored)
   - Run the data collection scripts in `src/collectors/` to fetch data from APIs:
     ```bash
     python src/collectors/open_meteo_api.py
     ```

5. **Set up environment variables (if needed):**
   - Create a `.env` file in the project root for any API keys or sensitive configs
   - Reference `python-dotenv` for loading environment variables

### Running the Project

- **Jupyter Notebooks:** Open notebooks in `notebooks/` for EDA and exploratory analysis
- **Streamlit Dashboard:** Launch the interactive app with:
  ```bash
  streamlit run app/main.py
  ```