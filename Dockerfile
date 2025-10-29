FROM docker.io/pytorch/pytorch


ARG gh_username=Reima
ARG service_home="/home/EasyOCR"

# Configure apt and install packages
RUN apt-get update -y && \
    apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-dev \
    git \
    python3 \
    # cleanup
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists

# Clone EasyOCR repo
RUN mkdir "$service_home" \
    && git clone "https://github.com/JaidedAI/EasyOCR.git" "$service_home" \
    && cd "$service_home" \
    && git remote add upstream "https://github.com/JaidedAI/EasyOCR.git" \
    && git pull upstream master

# Build EasyOCR
RUN cd "$service_home" \
    && python setup.py build_ext --inplace -j 4 \
    && python -m pip install -e .

# Crear directorio para la aplicación
WORKDIR /app

# Copiar los archivos de tu bot
COPY ./app /app/
COPY requirements.txt /app/requirements.txt

# Si tienes un requirements.txt, instálalo
RUN pip install -r ./app/requirements.txt

# Exponer puerto si es necesario (para webhooks)
EXPOSE 5900

# Comando para ejecutar el bot
CMD ["python3", "main.py"]