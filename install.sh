#!/bin/bash
set -e

echo "Installing dependencies for Python 3.11 in stages..."

# Stage 1: Core scientific packages
echo "Stage 1: Installing core scientific packages..."
pip install --no-cache-dir \
    numpy>=1.23.0 \
    pandas>=1.5.0 \
    scipy>=1.9.0 \
    matplotlib>=3.6.0 \
    Pillow>=9.5.0

# Stage 2: ML libraries
echo "Stage 2: Installing ML libraries..."
pip install --no-cache-dir \
    scikit-learn>=1.0.0 \
    xgboost>=1.4.2 \
    statsmodels>=0.13.1

# Stage 3: TensorFlow
echo "Stage 3: Installing TensorFlow..."
pip install --no-cache-dir tensorflow>=2.13.0

# Stage 4: Azure ML SDK
echo "Stage 4: Installing Azure ML SDK..."
pip install --no-cache-dir azureml-sdk

# Stage 5: Computer vision
echo "Stage 5: Installing computer vision libraries..."
pip install --no-cache-dir \
    opencv-python \
    opencv-python-headless \
    imutils

# Stage 6: Visualization
echo "Stage 6: Installing visualization libraries..."
pip install --no-cache-dir \
    plotly>=5.3.1 \
    seaborn>=0.11.2 \
    altair>=4.1.0

# Stage 7: Time series and statistical modeling
echo "Stage 7: Installing time series libraries..."
pip install --no-cache-dir \
    pystan \
    cmdstanpy \
    holidays

# Stage 8: Web frameworks
echo "Stage 8: Installing web frameworks..."
pip install --no-cache-dir \
    streamlit>=1.1.0 \
    Flask>=2.0.0 \
    gunicorn>=19.9.0

# Stage 9: Jupyter
echo "Stage 9: Installing Jupyter..."
pip install --no-cache-dir \
    notebook \
    ipykernel \
    ipython \
    jupyterlab-widgets

# Stage 10: Azure services
echo "Stage 10: Installing Azure services..."
pip install --no-cache-dir \
    azure-storage-blob \
    azure-identity \
    azure-keyvault-secrets

# Stage 11: MLOps
echo "Stage 11: Installing MLOps tools..."
pip install --no-cache-dir mlflow

# Stage 12: Data handling
echo "Stage 12: Installing data handling libraries..."
pip install --no-cache-dir \
    openpyxl \
    xlrd \
    XlsxWriter \
    kaggle \
    opendatasets

# Stage 13: Databricks
echo "Stage 13: Installing Databricks CLI..."
pip install --no-cache-dir databricks-cli

# Stage 14: Utilities
echo "Stage 14: Installing utilities..."
pip install --no-cache-dir \
    python-dateutil \
    pytz \
    requests \
    tqdm \
    pyyaml \
    click \
    python-box \
    gitpython \
    tabulate \
    kneed \
    autopep8

echo "Installation complete!"
echo "Verifying key packages..."
python -c "import numpy; import pandas; import tensorflow; import azureml.core; print('All key packages imported successfully!')"
