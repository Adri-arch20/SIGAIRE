from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class VisionData(BaseModel):
    model_config = ConfigDict(extra="allow")

    izquierda: float = 0.0
    centro: float = 0.0
    derecha: float = 0.0
    objeto: str = ""
    confianza: float = 0.0
    brillo: float = 0.0
    blur: float = 0.0


class SensorData(BaseModel):
    model_config = ConfigDict(extra="allow")

    pm25: Optional[float] = None
    pm10: Optional[float] = None

    pm25_raw: Optional[float] = None
    pm10_raw: Optional[float] = None

    pm25_filtered: Optional[float] = None
    pm10_filtered: Optional[float] = None

    pm25_std: Optional[float] = None
    pm10_std: Optional[float] = None

    pm25_min: Optional[float] = None
    pm25_max: Optional[float] = None
    pm10_min: Optional[float] = None
    pm10_max: Optional[float] = None

    sds011_estado: str = "SIN_DATOS"
    sds011_calibracion: str = "FABRICA"
    sds011_muestras: int = 0
    sds011_id: str = ""
    sds011_outliers: int = 0

    co2: Optional[float] = None
    temperatura: Optional[float] = None
    humedad: Optional[float] = None
    presion: Optional[float] = None


class TelemetryIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    robot: str = "MeteoBot"
    estado: str = "offline"
    modo: str = ""
    movimiento: str = "STOP"
    gesto: str = "AUTONOMO"
    esp32: str = "desconectado"
    vision: VisionData = VisionData()
    sensores: SensorData = SensorData()


# Datos recibidos por el puente Raspberry <- ESP32. No son medidas
# calibradas de concentracion: Sharp y BFS302 entregan voltajes/estados.
class SHT3xReading(BaseModel):
    estado: str = "SIN_DATOS"
    temperatura: FiniteFloat | None = None
    humedad: FiniteFloat | None = None


class SharpReading(BaseModel):
    estado: str = "SIN_DATOS"
    raw: FiniteFloat | None = None
    raw_min: int | None = None
    raw_max: int | None = None
    adc_mv: FiniteFloat | None = None
    vo_v: FiniteFloat | None = None
    adc_alto: bool | None = None


class BFS302Reading(BaseModel):
    estado: str = "SIN_DATOS"
    raw: FiniteFloat | None = None
    adc_mv: FiniteFloat | None = None
    aout_v: FiniteFloat | None = None
    dout: int | None = Field(default=None, ge=0, le=1)


class MG811Reading(BaseModel):
    estado: str = "SIN_DATOS"
    gpio: int = 35
    raw: FiniteFloat | None = None
    adc_mv: FiniteFloat | None = None
    aout_v: FiniteFloat | None = None
    co2_ppm: FiniteFloat | None = None
    calibrado: bool = False
    estable_10min: bool = False
    deriva_10min_mv: FiniteFloat | None = None
    rango_10min_mv: FiniteFloat | None = None
    alimentacion_v: FiniteFloat | None = None
    linea_base_adc_mv: FiniteFloat | None = None
    delta_aout_mv: FiniteFloat | None = None
    evento_senal: str = "SIN_BASE"
    umbral_evento_aout_mv: FiniteFloat | None = None
    listo_para_referencia: bool = False
    ppm_validado_tercer_punto: bool = False
    error_validacion_pct: FiniteFloat | None = None
    metodo_ppm: str = ""


class Esp32MotorsReading(BaseModel):
    izquierdo: int = Field(default=0, ge=-255, le=255)
    derecho: int = Field(default=0, ge=-255, le=255)
    maximo: int = Field(default=255, ge=1, le=255)
    activos: bool = False


class Esp32SensorsIn(BaseModel):
    estado: str = "SIN_DATOS"
    uptime_ms: int | None = Field(default=None, ge=0)
    movimiento: str | None = None
    motores: Esp32MotorsReading | None = None
    sht3x: SHT3xReading = Field(default_factory=SHT3xReading)
    sharp: SharpReading = Field(default_factory=SharpReading)
    bfs302: BFS302Reading = Field(default_factory=BFS302Reading)
    mg811: MG811Reading = Field(default_factory=MG811Reading)


class SDS011SensorsIn(BaseModel):
    """Lectura independiente del SDS011 conectado por USB/serial a Raspberry Pi."""
    model_config = ConfigDict(extra="allow")

    pm25: FiniteFloat | None = None
    pm10: FiniteFloat | None = None
    pm25_raw: FiniteFloat | None = None
    pm10_raw: FiniteFloat | None = None
    pm25_filtered: FiniteFloat | None = None
    pm10_filtered: FiniteFloat | None = None
    pm25_std: FiniteFloat | None = None
    pm10_std: FiniteFloat | None = None
    pm25_min: FiniteFloat | None = None
    pm25_max: FiniteFloat | None = None
    pm10_min: FiniteFloat | None = None
    pm10_max: FiniteFloat | None = None
    sds011_estado: str = "SIN_DATOS"
    sds011_calibracion: str = "FABRICA"
    sds011_muestras: int = Field(default=0, ge=0)
    sds011_id: str = ""
    sds011_puerto: str = ""
    sds011_tramas_invalidas: int = Field(default=0, ge=0)
    sds011_outliers: int = Field(default=0, ge=0)
    sds011_calentamiento_restante: int | None = Field(default=None, ge=0)
    sds011_edad_lectura_s: FiniteFloat | None = None
