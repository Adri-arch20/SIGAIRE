Coloca aqui un modelo YOLO personalizado si deseas usarlo.

Ejemplo:
  robot/models/meteobot_campus.pt

Luego ejecuta:
  METEOBOT_YOLO_MODEL=/ruta/al/proyecto/robot/models/meteobot_campus.pt ./scripts/run_robot_autonomo.sh

Si no defines METEOBOT_YOLO_MODEL, el programa intenta usar yolo11n.pt.
