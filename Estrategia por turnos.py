import random
import os
import json
from enum import Enum

# Colorama removido: no dependemos de él (evita errores si no está instalado)
HAS_COLORAMA = False

# --- CONSTANTES DE JUEGO ---
XP_POR_NIVEL_BASE = 100
VIDA_INICIAL_JUGADOR = 100
MANA_INICIAL_JUGADOR = 50
VIDA_GANADA_POR_NIVEL = 20
MANA_GANADO_POR_NIVEL = 10
CANTIDAD_CURACION_POCION_VIDA = 50
CANTIDAD_CURACION_POCION_MANA = 30

# Mecánicas añadidas
CRIT_CHANCE = 0.12
CRIT_MULT = 1.75

# Probabilidades de fallo
HERO_MISS_CHANCE = 0.10   # 10% probabilidad de fallar para el héroe
ENEMY_MISS_CHANCE = 0.50  # 50% probabilidad de fallar para los enemigos

class Elemento(Enum):
    TIEMPO = "Tiempo"
    ESPACIO = "Espacio"
    ENERGIA = "Energía"
    MATERIA = "Materia"

class Personaje:
    """
    Representa al personaje principal del jugador.
    """
    def __init__(self, nombre):
        self.nombre = nombre
        self.nivel = 1
        self.xp = 0
        # Estadísticas base (sin buffs temporales)
        self.vida_base = VIDA_INICIAL_JUGADOR
        self.mana_base = MANA_INICIAL_JUGADOR
        self.ataque = 10
        self.defensa_base = 8

        # Buffs temporales (lista para permitir apilamiento y expiración individual)
        self.buffs = []  # cada buff: {'tipo':'defensa', 'incremento':int, 'turnos':int, 'porcentaje':int}

        # Estadísticas actuales
        self.vida = self.max_vida
        self.mana = self.max_mana
        self.defensa = self.defensa_base

        self.velocidad = 5
        self.elemento = Elemento.TIEMPO
        self.habilidades = ["Explosión de Energía"]  # Habilidad inicial
        self.inventario = {"Poción de Vida": 3, "Poción de Mana": 2}
        # Estados (poison, burn, stun, etc.)
        self.estados = {}

        # Equipo sencillo: arma y armadura
        self.equipo = {"arma": None, "armadura": None}

        # Puntos de talento y árbol simple
        self.puntos_talento = 0
        self.habilidades_pasivas = {
            "Furia": {"desc": "+2 ataque", "costo": 1, "aplicado": False},
            "Coraza": {"desc": "+2 defensa", "costo": 1, "aplicado": False}
        }

        # Mensajes variables
        self.mensajes_ataque = [
            "¡Un golpe certero!",
            "¡Impacto devastador!",
            "¡Golpe rápido y preciso!"
        ]

    @property
    def max_vida(self):
        return int(self.vida_base + (self.nivel - 1) * VIDA_GANADA_POR_NIVEL)

    @property
    def max_mana(self):
        return int(self.mana_base + (self.nivel - 1) * MANA_GANADO_POR_NIVEL)

    def subir_nivel(self):
        """
        Procesa subida de nivel mientras haya XP suficiente.
        Actualiza vida/mana/estadísticas base y respeta los buffs actuales.
        """
        subio = False
        while self.xp >= self.nivel * XP_POR_NIVEL_BASE:
            xp_necesario = self.nivel * XP_POR_NIVEL_BASE
            self.xp -= xp_necesario
            self.nivel += 1

            # Aumentos base por nivel
            self.vida_base += VIDA_GANADA_POR_NIVEL
            self.mana_base += MANA_GANADO_POR_NIVEL
            # Incrementos moderados por nivel (más predecibles)
            self.ataque += 2
            self.defensa_base += 1

            # Restaurar vida y maná al máximo tras subir
            self.vida = self.max_vida
            self.mana = self.max_mana

            # Recalcular defensa actual respetando buff acumulado
            total_inc = sum(b.get('incremento', 0) for b in self.buffs if b.get('tipo') == 'defensa')
            self.defensa = self.defensa_base + total_inc

            print(f"\n¡{self.nombre} ha subido al nivel {self.nivel}!")
            # Mejora aleatoria leve
            stat = random.choice(['ataque', 'defensa_base', 'velocidad'])
            aumento = random.randint(2, 5)
            if stat == 'defensa_base':
                self.defensa_base += aumento
                # actualizar defensa actual
                total_inc = sum(b.get('incremento', 0) for b in self.buffs if b.get('tipo') == 'defensa')
                self.defensa = self.defensa_base + total_inc
                actual_val = self.defensa_base
                stat_name = "defensa"
            else:
                setattr(self, stat, getattr(self, stat) + aumento)
                actual_val = getattr(self, stat)
                stat_name = stat
            print(f"¡{stat_name.capitalize()} aumentó en {aumento} a {actual_val}!")
            subio = True
            # Otorgar punto de talento por nivel
            self.puntos_talento += 1
        return subio

    def usar_habilidad(self, habilidad, enemigos, target_index=None):
        """
        Ejecuta la habilidad elegida. Retorna un mensaje con el resultado.
        `target_index` es opcional y se usa para habilidades dirigidas.
        """
        costos = {
            "Distorsión Temporal": 15,
            "Plegado Espacial": 20,
            "Singularidad Cuántica": 30,
            "Explosión de Energía": 25,
            "Rayo de Energía Pura": 22,
            "Transmutación de Materia": 5,
            "Bastión Temporal": 12
        }
        costo = costos.get(habilidad, 0)
        if self.mana < costo:
            return f"No tienes suficiente maná para usar {habilidad} (requiere {costo} MP)."

        enemigos_vivos = [e for e in enemigos if e.vida > 0]
        mensaje = ""

        # Habilidad especial: Transmutación consume vida para recuperar maná
        if habilidad == "Transmutación de Materia":
            costo_vida = 20
            if self.vida <= costo_vida:
                return "No tienes suficiente vida para usar Transmutación de Materia."
            self.vida -= costo_vida
            self.mana = max(0, self.mana - costo)
            mana_recuperado = min(40, self.max_mana - self.mana)
            self.mana += mana_recuperado
            return f"Sacrificas {costo_vida} HP para ganar {mana_recuperado} MP. (-{costo} MP)"

        # Consumo normal de maná
        self.mana -= costo

        # Para habilidades de daño dirigidas/combativas aplicamos probabilidad de fallo del héroe
        habilidades_de_daño = {"Singularidad Cuántica", "Explosión de Energía", "Rayo de Energía Pura"}
        if habilidad in habilidades_de_daño:
            if random.random() < HERO_MISS_CHANCE:
                return f"Fallaste al usar {habilidad}. (-{costo} MP)"

        if habilidad == "Distorsión Temporal":
            for enemigo in enemigos_vivos:
                enemigo.velocidad = max(1, enemigo.velocidad - 2)
            mensaje = f"¡Has ralentizado a los enemigos vivos! (-2 velocidad, -{costo} MP)"
        elif habilidad == "Plegado Espacial":
            curado = min(self.max_vida - self.vida, 50)
            self.restaurar_vida(curado)
            mensaje = f"¡Has restaurado {curado} puntos de vida! (-{costo} MP)"
        elif habilidad == "Singularidad Cuántica":
            derrotados = 0
            for enemigo in enemigos_vivos:
                enemigo.vida -= 30
                if enemigo.vida <= 0:
                    derrotados += 1
            mensaje = f"¡Has infligido 30 puntos de daño a todos los enemigos vivos! (-{costo} MP)"
            if derrotados > 0:
                mensaje += f" Derrotaste a {derrotados} enemigo(s)."
        elif habilidad == "Explosión de Energía":
            derrotados = 0
            for enemigo in enemigos_vivos:
                enemigo.vida -= 20
                enemigo.defensa = max(1, enemigo.defensa - 2)
                if enemigo.vida <= 0:
                    derrotados += 1
            mensaje = f"¡Has infligido 20 puntos de daño y reducido la defensa de los enemigos vivos! (-{costo} MP)"
            if derrotados > 0:
                mensaje += f" Derrotaste a {derrotados} enemigo(s)."
        elif habilidad == "Rayo de Energía Pura":
            if not enemigos_vivos:
                return "No hay enemigos vivos para apuntar."
            if target_index is None:
                return "need_target"
            if not (0 <= target_index < len(enemigos_vivos)):
                return "Selección inválida."
            enemigo = enemigos_vivos[target_index]
            danio = self.ataque + 25
            arma = self.equipo.get("arma")
            if arma and isinstance(arma, dict):
                danio += arma.get("ataque", 0)
            if random.random() < CRIT_CHANCE:
                danio = int(danio * CRIT_MULT)
                crit_msg = " (¡Crítico!)"
            else:
                crit_msg = ""
            enemigo.vida -= danio
            mensaje = f"¡Lanzas un Rayo de Energía Pura sobre {enemigo.nombre} por {danio} de daño{crit_msg}! (-{costo} MP)"
            if enemigo.vida <= 0:
                mensaje += f"\n¡{enemigo.nombre} ha sido desintegrado!"
        elif habilidad == "Bastión Temporal":
            # buff de defensa del 10% durante 3 turnos
            mensaje = self.aplicar_buff_defensa(10, turnos=3)
        else:
            # habilidad desconocida -> ya se descontó maná, devolvemos maná y mensaje
            self.mana += costo
            mensaje = "Habilidad no reconocida."
        return mensaje

    def usar_objeto(self, objeto):
        if objeto == "Poción de Vida":
            if self.inventario.get(objeto, 0) > 0:
                if self.vida >= self.max_vida:
                    return "Ya tienes la vida al máximo."
                cantidad = min(CANTIDAD_CURACION_POCION_VIDA, self.max_vida - self.vida)
                self.restaurar_vida(cantidad)
                self.inventario[objeto] -= 1
                return f"Usaste una Poción de Vida y recuperaste {cantidad} puntos de vida."
            else:
                return "No tienes Pociones de Vida."
        elif objeto == "Poción de Mana":
            if self.inventario.get(objeto, 0) > 0:
                if self.mana >= self.max_mana:
                    return "Ya tienes el maná al máximo."
                cantidad = min(CANTIDAD_CURACION_POCION_MANA, self.max_mana - self.mana)
                self.mana = min(self.max_mana, self.mana + cantidad)
                self.inventario[objeto] -= 1
                return f"Usaste una Poción de Mana y recuperaste {cantidad} puntos de maná."
            else:
                return "No tienes Pociones de Mana."
        else:
            return "No tienes ese objeto disponible."

    def restaurar_vida(self, cantidad):
        self.vida = min(self.max_vida, int(self.vida + cantidad))

    # --- Estados (poison, burn, stun) ---
    def aplicar_estado(self, nombre, efecto):
        """efecto: dict con keys 'dmg' y 'turnos' o 'stun':True"""
        existing = self.estados.get(nombre)
        if existing:
            existing['turnos'] = max(existing.get('turnos', 0), efecto.get('turnos', 0))
        else:
            self.estados[nombre] = efecto.copy()
        return f"Estado {nombre} aplicado ({efecto})."

    def procesar_estados(self):
        mensajes = []
        to_remove = []
        for nombre, data in list(self.estados.items()):
            if nombre == 'stun':
                data['turnos'] -= 1
                mensajes.append(f"{self.nombre} está aturdido y no puede actuar ({data['turnos']} turnos restantes).")
                if data['turnos'] <= 0:
                    to_remove.append(nombre)
            else:
                dmg = data.get('dmg', 0)
                self.vida -= dmg
                data['turnos'] -= 1
                mensajes.append(f"{self.nombre} sufre {dmg} de {nombre} ({data['turnos']} turnos restantes).")
                if data['turnos'] <= 0:
                    to_remove.append(nombre)
        for r in to_remove:
            del self.estados[r]
            mensajes.append(f"{self.nombre} ya no sufre {r}.")
        return mensajes

    def equipar(self, item):
        # item: dict con 'tipo' 'arma'/'armadura', 'nombre', y stats
        if not isinstance(item, dict) or 'tipo' not in item:
            return "Ítem inválido."
        tipo = item['tipo']
        self.equipo[tipo] = item
        return f"Has equipado {item.get('nombre', 'objeto')} ({tipo})."

    # --- Serialización ---
    def to_dict(self):
        return {
            'nombre': self.nombre,
            'nivel': self.nivel,
            'xp': self.xp,
            'vida_base': self.vida_base,
            'mana_base': self.mana_base,
            'ataque': self.ataque,
            'defensa_base': self.defensa_base,
            'vida': self.vida,
            'mana': self.mana,
            'defensa': self.defensa,
            'velocidad': self.velocidad,
            'elemento': self.elemento.name,
            'habilidades': self.habilidades,
            'inventario': self.inventario,
            'estados': self.estados,
            'equipo': self.equipo,
            'puntos_talento': self.puntos_talento,
            'habilidades_pasivas': self.habilidades_pasivas,
            'buffs': self.buffs,
        }

    @staticmethod
    def from_dict(d):
        p = Personaje(d.get('nombre', 'Heroe'))
        p.nivel = d.get('nivel', 1)
        p.xp = d.get('xp', 0)
        p.vida_base = d.get('vida_base', p.vida_base)
        p.mana_base = d.get('mana_base', p.mana_base)
        p.ataque = d.get('ataque', p.ataque)
        p.defensa_base = d.get('defensa_base', p.defensa_base)
        p.vida = d.get('vida', p.max_vida)
        p.mana = d.get('mana', p.max_mana)
        p.defensa = d.get('defensa', p.defensa_base)
        p.velocidad = d.get('velocidad', p.velocidad)
        elemento_name = d.get('elemento')
        if elemento_name:
            try:
                p.elemento = Elemento[elemento_name]
            except Exception:
                p.elemento = Elemento.TIEMPO
        p.habilidades = d.get('habilidades', p.habilidades)
        p.inventario = d.get('inventario', p.inventario)
        p.estados = d.get('estados', {})
        p.equipo = d.get('equipo', p.equipo)
        p.puntos_talento = d.get('puntos_talento', 0)
        p.habilidades_pasivas = d.get('habilidades_pasivas', p.habilidades_pasivas)
        p.buffs = d.get('buffs', [])
        return p

    # --- Buffs de defensa ---
    def aplicar_buff_defensa(self, porcentaje, turnos=3):
        """
        Aplica un buff temporal sobre la defensa base.
        Retorna mensaje descriptivo.
        """
        if porcentaje <= 0 or turnos <= 0:
            return "Buff inválido."
        incremento = int(self.defensa_base * (porcentaje / 100.0))
        if incremento <= 0:
            incremento = 1
        buff = {'tipo': 'defensa', 'incremento': incremento, 'turnos': turnos, 'porcentaje': porcentaje}
        self.buffs.append(buff)
        # recalcular defensa actual sumando todos los buffs de defensa
        total_inc = sum(b.get('incremento', 0) for b in self.buffs if b.get('tipo') == 'defensa')
        self.defensa = self.defensa_base + total_inc
        return f"Tu defensa aumentó en {incremento} ({porcentaje}%) durante {turnos} turnos."

    def actualizar_buffs(self):
        """
        Decrementa duración de buffs y los remueve cuando expiran.
        Debe llamarse al final del turno enemigo.
        """
        mensajes = []
        to_remove = []
        for i, b in enumerate(self.buffs):
            b['turnos'] -= 1
            if b['turnos'] <= 0:
                to_remove.append(i)
        # eliminar buffs expirados
        for idx in reversed(to_remove):
            buff = self.buffs.pop(idx)
            mensajes.append(f"El buff {buff.get('tipo')} de {buff.get('porcentaje', '')}% ha terminado.")
        # recalcular defensa
        total_inc = sum(b.get('incremento', 0) for b in self.buffs if b.get('tipo') == 'defensa')
        self.defensa = self.defensa_base + total_inc
        return "\n".join(mensajes) if mensajes else None

class Enemigo:
    def __init__(self, nivel_jugador, elemento_jugador):
        elementos = list(Elemento)
        opciones = [e for e in elementos if e != elemento_jugador]
        self.elemento = random.choice(opciones) if opciones else random.choice(elementos)
        self.nivel = max(1, nivel_jugador + random.randint(-1, 2))
        self.vida_max = 50 + (self.nivel * 10)
        self.vida = self.vida_max
        self.ataque = 8 + (self.nivel * 2)
        self.defensa = 5 + (self.nivel * 1)
        self.velocidad = 3 + (self.nivel * 1)
        self.mana = 0

        tipos_enemigo = ['Guerrero', 'Mago', 'Sanador', 'Clon', 'Asesino', 'Tanque']
        pesos = [40, 30, 20, 10, 15, 25]
        tipo = random.choices(tipos_enemigo, weights=pesos, k=1)[0]

        if tipo == 'Guerrero':
            self.ataque = int(self.ataque * 1.5)
        elif tipo == 'Mago':
            self.mana = 30 + (self.nivel * 5)
        elif tipo == 'Sanador':
            self.vida_max = int(self.vida_max * 0.8)
            self.vida = self.vida_max
            self.defensa = int(self.defensa * 1.2)
        elif tipo == 'Clon':
            self.elemento = elemento_jugador
            self.velocidad = int(self.velocidad * 2)
        elif tipo == 'Asesino':
            self.ataque = int(self.ataque * 1.2)
            self.velocidad = int(self.velocidad * 1.5)
        elif tipo == 'Tanque':
            self.vida_max = int(self.vida_max * 1.5)
            self.vida = self.vida_max
            self.defensa = int(self.defensa * 1.5)

        self.tipo = tipo
        # Pequeña probabilidad de que el enemigo sea un jefe con fases
        if random.random() < 0.08:
            self.tipo = 'Jefe'
            self.vida_max = int(self.vida_max * 2.5)
            self.vida = self.vida_max
            self.ataque = int(self.ataque * 1.8)
            self.defensa = int(self.defensa * 1.5)
            self.velocidad = max(1, int(self.velocidad * 1.2))
            self.fase = 1
        self.nombre = f"{self.tipo} de {self.elemento.value} (Nvl {self.nivel})"
        # Inicializar estados por defecto (poison, burn, stun, etc.)
        self.estados = {}

    def _accion_jefe(self, jugador, defensa_jugador):
        hp_ratio = self.vida / max(1, self.vida_max)
        if hp_ratio > 0.66:
            # fase 1: ataques fuertes y ocasional hechizo
            if random.random() < 0.3:
                return self.lanzar_hechizo(jugador, defensa_jugador)
            return self.atacar(jugador, defensa_jugador)
        elif hp_ratio > 0.33:
            # fase 2: usa habilidades, aplica burn y reduce defensa del jugador
            if random.random() < 0.5:
                jugador.aplicar_estado('burn', {'dmg': 5 + self.nivel, 'turnos': 3})
                return f"{self.nombre} lanza un hechizo ígneo y aplica quemadura!"
            else:
                # ataque más potente
                danio = max(0, (self.ataque * 2) - defensa_jugador)
                jugador.vida -= danio
                return f"{self.nombre} entra en rabia y ataca por {danio} de daño!"
        else:
            # fase 3: berserk, puede curarse un poco
            if random.random() < 0.4:
                cura = int(self.vida_max * 0.08)
                self.vida = min(self.vida_max, self.vida + cura)
                return f"{self.nombre} se regenera {cura} de vida y entra en furia!"
            danio = max(0, (self.ataque * 3) - defensa_jugador)
            jugador.vida -= danio
            return f"{self.nombre} desata su fase final y golpea por {danio} de daño!"
        

    def aplicar_estado(self, nombre, efecto):
        existing = self.estados.get(nombre)
        if existing:
            existing['turnos'] = max(existing.get('turnos', 0), efecto.get('turnos', 0))
        else:
            self.estados[nombre] = efecto.copy()
        return f"{self.nombre} sufre ahora {nombre}."

    def procesar_estados(self):
        mensajes = []
        to_remove = []
        for nombre, data in list(self.estados.items()):
            if nombre == 'stun':
                data['turnos'] -= 1
                mensajes.append(f"{self.nombre} está aturdido ({data['turnos']} turnos restantes).")
                if data['turnos'] <= 0:
                    to_remove.append(nombre)
            else:
                dmg = data.get('dmg', 0)
                self.vida -= dmg
                data['turnos'] -= 1
                mensajes.append(f"{self.nombre} sufre {dmg} de {nombre}. ({data['turnos']} turnos restantes)")
                if data['turnos'] <= 0:
                    to_remove.append(nombre)
        for r in to_remove:
            del self.estados[r]
            mensajes.append(f"{self.nombre} ya no sufre {r}.")
        return mensajes

    def accion(self, jugador, defensa_jugador):
        if getattr(self, 'tipo', None) == 'Jefe':
            return self._accion_jefe(jugador, defensa_jugador)
        if self.tipo == 'Sanador' and self.vida < self.vida_max:
            return self.curar()
        elif self.tipo == 'Mago' and random.random() < 0.6:
            return self.lanzar_hechizo(jugador, defensa_jugador)
        else:
            return self.atacar(jugador, defensa_jugador)

    def atacar(self, jugador, defensa_jugador):
        # probabilidad de fallo del enemigo
        if random.random() < ENEMY_MISS_CHANCE:
            return f"{self.nombre} falla su ataque."
        danio = max(0, self.ataque - defensa_jugador // 2)
        jugador.vida -= danio
        return f"{self.nombre} ataca por {danio} de daño!"

    def curar(self):
        curacion = int(self.defensa * 1.5)
        self.vida = min(self.vida_max, self.vida + curacion)
        return f"{self.nombre} se cura {curacion} puntos de vida!"

    def lanzar_hechizo(self, jugador, defensa_jugador):
        # probabilidad de fallo del enemigo al lanzar hechizo
        if random.random() < ENEMY_MISS_CHANCE:
            return f"{self.nombre} falla su hechizo."
        danio = max(0, (self.ataque * 2) - defensa_jugador)
        jugador.vida -= danio
        return f"{self.nombre} lanza un hechizo de {self.elemento.value} por {danio} de daño!"

class FabricaEnemigos:
    @staticmethod
    def crear_enemigo(nivel_jugador, elemento_jugador):
        return Enemigo(nivel_jugador, elemento_jugador)

class Juego:
    def __init__(self, jugador=None):
        if jugador:
            self.jugador = jugador
        else:
            nombre_heroe = input("Nombre de tu héroe: ")
            self.jugador = Personaje(nombre_heroe)

        self.nivel_actual = 1
        self.habilidades_disponibles = {
            2: "Distorsión Temporal",
            3: "Bastión Temporal",
            4: "Plegado Espacial",
            6: "Singularidad Cuántica",
            8: "Rayo de Energía Pura",
            10: "Transmutación de Materia"
        }
        self.logros = []
        self.archivo_guardado = "progreso_guardado.pkl"

        # Sincroniza y notifica habilidades que por nivel ya debería tener el jugador
        nuevas = self._sincronizar_habilidades()
        if nuevas:
            for hab in nuevas:
                print(f"¡Habilidad adquirida al iniciar/cargar: {hab}!")

    def guardar_progreso(self):
        try:
            data = self.to_dict()
            with open(self.archivo_guardado, "w", encoding='utf-8') as archivo:
                json.dump(data, archivo, ensure_ascii=False, indent=2)
            print("Progreso guardado.")
        except IOError as e:
            print(f"Error al guardar el progreso: {e}")

    @staticmethod
    def cargar_progreso(archivo):
        if not os.path.exists(archivo):
            return None
        try:
            with open(archivo, "r", encoding='utf-8') as f:
                data = json.load(f)
                juego_cargado = Juego.from_dict(data)
                print("Progreso cargado exitosamente.")
                try:
                    nuevas = juego_cargado._sincronizar_habilidades()
                    if nuevas:
                        for hab in nuevas:
                            print(f"¡Habilidad añadida al cargar: {hab}!")
                except Exception:
                    pass
                return juego_cargado
        except (json.JSONDecodeError, IOError) as e:
            print(f"No se pudo cargar el progreso guardado. Error: {e}")
            return None

    def verificar_logros(self):
        if self.jugador.nivel >= 5 and "Maestro del Tiempo" not in self.logros:
            self.logros.append("Maestro del Tiempo")
            print("¡Logro desbloqueado: Maestro del Tiempo!")

    def generar_dropeo(self, enemigos):
        """Genera un drop simple tras la batalla: pociones o equipo básico."""
        posible = random.random()
        if posible < 0.25:
            # Poción
            tipo = random.choice(["Poción de Vida", "Poción de Mana"])
            self.jugador.inventario[tipo] = self.jugador.inventario.get(tipo, 0) + 1
            print(f"Has encontrado una {tipo} en los restos del combate.")
        elif posible < 0.5:
            # arma básica
            arma = {"tipo": "arma", "nombre": "Daga Serrada", "ataque": 3}
            print(f"Has encontrado un arma: {arma['nombre']} (+{arma['ataque']} ataque).")
            # pregunta si equipar
            opcion = input("¿Deseas equiparla? (s/n): ").lower()
            if opcion == 's':
                msg = self.jugador.equipar(arma)
                print(msg)
            else:
                # guardarla como objeto en inventario simple
                self.jugador.inventario.setdefault('Objetos', [])
                self.jugador.inventario['Objetos'].append(arma)
        elif posible < 0.75:
            # armadura básica
            arm = {"tipo": "armadura", "nombre": "Grebas Oxidadas", "defensa": 2}
            print(f"Has encontrado una armadura: {arm['nombre']} (+{arm['defensa']} defensa).")
            opcion = input("¿Deseas equiparla? (s/n): ").lower()
            if opcion == 's':
                msg = self.jugador.equipar(arm)
                print(msg)
            else:
                self.jugador.inventario.setdefault('Objetos', [])
                self.jugador.inventario['Objetos'].append(arm)
        else:
            print("No encontraste nada valioso en el combate.")

    def _sincronizar_habilidades(self):
        """
        Otorga al jugador todas las habilidades en 'habilidades_disponibles'
        cuyo requisito de nivel ya fue alcanzado y que aún no tenga.
        Retorna la lista de habilidades nuevas añadidas.
        """
        nuevas = []
        for nivel_req, habilidad in sorted(self.habilidades_disponibles.items()):
            if self.jugador.nivel >= nivel_req and habilidad not in self.jugador.habilidades:
                self.jugador.habilidades.append(habilidad)
                nuevas.append(habilidad)
        return nuevas

    def to_dict(self):
        return {
            'jugador': self.jugador.to_dict(),
            'nivel_actual': self.nivel_actual,
            'habilidades_disponibles': self.habilidades_disponibles,
            'logros': self.logros,
            'archivo_guardado': self.archivo_guardado,
        }

    @staticmethod
    def from_dict(d):
        jugador_data = d.get('jugador')
        jugador = Personaje.from_dict(jugador_data) if jugador_data else None
        juego = Juego(jugador=jugador)
        juego.nivel_actual = d.get('nivel_actual', juego.nivel_actual)
        juego.habilidades_disponibles = d.get('habilidades_disponibles', juego.habilidades_disponibles)
        juego.logros = d.get('logros', [])
        juego.archivo_guardado = d.get('archivo_guardado', juego.archivo_guardado)
        return juego

    def batalla(self):
        print(f"\n=== NIVEL {self.nivel_actual} ===")
        print(f"\n=== {self.jugador.nombre.upper()} ===")
        print(f"Nivel: {self.jugador.nivel} | Vida: {self.jugador.vida}/{self.jugador.max_vida} | Mana: {self.jugador.mana}/{self.jugador.max_mana}")

        enemigos_iniciales = [FabricaEnemigos.crear_enemigo(self.jugador.nivel, self.jugador.elemento) for _ in range(random.randint(2, 4))]
        enemigos = list(enemigos_iniciales)

        while any(e.vida > 0 for e in enemigos) and self.jugador.vida > 0:
            # --- Turno del jugador ---
            print("\n" + "-"*10 + " TU TURNO " + "-"*10)
            print(f"Jugador: {self.jugador.vida} HP | {self.jugador.mana} MP")
            # Procesar estados del jugador al inicio del turno
            pre_stun = 'stun' in self.jugador.estados
            est_msgs = self.jugador.procesar_estados()
            for m in est_msgs:
                print(m)
            enemigos_vivos = [e for e in enemigos if e.vida > 0]
            for i, e in enumerate(enemigos_vivos):
                print(f"Enemigo {i+1}: {e.nombre} - {e.vida} HP")
            
            accion_valida = False
            defendiendo = False
            # Si estaba aturdido antes de procesar estados, pierde el turno
            if pre_stun:
                print("Estás aturdido y pierdes este turno.")
            else:
                while not accion_valida:
                    accion = input("\nAcción [A]tacar, [H]abilidad, [D]efensa, [O]bjeto, [G]uardar: ").upper()
                    if accion not in ["A", "H", "D", "O", "G"]:
                        print("Acción no válida. Intenta de nuevo.")
                        continue

                    accion_valida = True # Asumimos que la acción será válida

                    if accion == "G":
                        self.guardar_progreso()
                        accion_valida = False # Permitir otra acción después de guardar
                        continue
                    if accion == "H":
                        if not self.jugador.habilidades:
                            print("No tienes habilidades disponibles.")
                            accion_valida = False
                            continue
                        print("Habilidades disponibles:")
                        for i, habilidad in enumerate(self.jugador.habilidades):
                            print(f"{i+1}. {habilidad}")
                        try:
                            eleccion = int(input("Elige una habilidad (0 para cancelar): "))
                        except ValueError:
                            print("Entrada inválida. Introduce un número.")
                            accion_valida = False
                            continue
                        if eleccion == 0:
                            accion_valida = False
                            continue
                        if 1 <= eleccion <= len(self.jugador.habilidades):
                            hab_sel = self.jugador.habilidades[eleccion - 1]
                            # Si la habilidad necesita objetivo, pedirlo aquí
                            if hab_sel == 'Rayo de Energía Pura':
                                if not enemigos_vivos:
                                    print("No hay enemigos vivos para esa habilidad.")
                                    accion_valida = False
                                    continue
                                print("Elige un enemigo para apuntar con el rayo:")
                                for i, e in enumerate(enemigos_vivos):
                                    print(f"{i+1}. {e.nombre} - {e.vida} HP")
                                try:
                                    idx = int(input("Número de enemigo (0 para cancelar): "))
                                except ValueError:
                                    print("Entrada inválida. Introduce un número.")
                                    accion_valida = False
                                    continue
                                if idx == 0:
                                    accion_valida = False
                                    continue
                                if not (1 <= idx <= len(enemigos_vivos)):
                                    print("Selección inválida.")
                                    accion_valida = False
                                    continue
                                resultado = self.jugador.usar_habilidad(hab_sel, enemigos, target_index=idx-1)
                                print(resultado)
                            else:
                                resultado = self.jugador.usar_habilidad(hab_sel, enemigos)
                                print(resultado)
                        else:
                            print("Selección inválida.")
                            accion_valida = False
                    elif accion == "D":
                        print("Te preparas para defenderte. Tu defensa se duplicará para el siguiente ataque.")
                        defendiendo = True
                    elif accion == "O":
                        if not self.jugador.inventario or all(v == 0 for v in self.jugador.inventario.values()):
                            print("No tienes objetos disponibles.")
                            accion_valida = False
                            continue
                        items_disponibles = [item for item, count in self.jugador.inventario.items() if count > 0]
                        print("Objetos disponibles:")
                        for i, item in enumerate(items_disponibles):
                            print(f"{i+1}. {item} ({self.jugador.inventario[item]})")
                        try:
                            eleccion = int(input("Elige un objeto (0 para cancelar): "))
                        except ValueError:
                            print("Entrada inválida. Introduce un número.")
                            accion_valida = False
                            continue
                        if eleccion == 0:
                            accion_valida = False
                            continue
                        if 1 <= eleccion <= len(items_disponibles):
                            objeto_elegido = items_disponibles[eleccion - 1]
                            resultado = self.jugador.usar_objeto(objeto_elegido)
                            print(resultado)
                        else:
                            print("Selección inválida.")
                            accion_valida = False
                            continue
                    elif accion == "A":
                        enemigos_vivos_ataque = [e for e in enemigos if e.vida > 0]
                        if not enemigos_vivos_ataque:
                            print("No hay enemigos vivos para atacar.")
                            accion_valida = False
                            continue
                        print("Elige enemigo a atacar:")
                        for i, e in enumerate(enemigos_vivos_ataque):
                            print(f"{i+1}. {e.nombre} - {e.vida} HP")
                        try:
                            idx = int(input("Número de enemigo (0 para cancelar): "))
                        except ValueError:
                            print("Entrada inválida. Introduce un número.")
                            accion_valida = False
                            continue
                        if idx == 0:
                            accion_valida = False
                            continue
                        if 1 <= idx <= len(enemigos_vivos_ataque):
                            enemigo = enemigos_vivos_ataque[idx - 1]
                            # chequeo de fallo del héroe
                            if random.random() < HERO_MISS_CHANCE:
                                print("¡Fallaste tu ataque!")
                            else:
                                # calcular daño con arma y crítico
                                arma = self.jugador.equipo.get('arma')
                                bonus_arma = arma.get('ataque', 0) if arma and isinstance(arma, dict) else 0
                                danio = max(0, (self.jugador.ataque + bonus_arma) - enemigo.defensa // 2)
                                if random.random() < CRIT_CHANCE:
                                    danio = int(danio * CRIT_MULT)
                                    print("¡Golpe crítico!")
                                enemigo.vida -= danio
                                print(f"¡Atacaste a {enemigo.nombre} por {danio} de daño!")
                                if enemigo.vida <= 0:
                                    print(f"¡{enemigo.nombre} ha sido derrotado!")
                        else:
                            print("Selección inválida.")
                            accion_valida = False
            
            # --- Turno de los enemigos ---
            enemigos = [e for e in enemigos if e.vida > 0] # Actualizar lista de enemigos vivos
            if any(e.vida > 0 for e in enemigos):
                print("\n" + "-"*10 + " TURNO ENEMIGO " + "-"*10)
                
            defensa_actual_jugador = self.jugador.defensa * 2 if defendiendo else self.jugador.defensa
            
            for enemigo in enemigos:
                if enemigo.vida > 0 and self.jugador.vida > 0:
                    pre_stun_e = 'stun' in enemigo.estados
                    msgs = enemigo.procesar_estados()
                    for m in msgs:
                        print(m)
                    if pre_stun_e:
                        print(f"{enemigo.nombre} está aturdido y pierde su turno.")
                        continue
                    resultado = enemigo.accion(self.jugador, defensa_actual_jugador)
                    print(resultado)
                    
            # Actualizar duraciones de buffs del jugador (se decrementan después del turno enemigo)
            msg_buff = self.jugador.actualizar_buffs()
            if msg_buff:
                print(msg_buff)
                    
            # Comprobar si el jugador fue derrotado
            if self.jugador.vida <= 0:
                print("\n¡Has sido derrotado!")
                return False
        
        # --- Fin de la batalla ---
        if self.jugador.vida > 0:
            # Posible dropeo tras la batalla
            try:
                self.generar_dropeo(enemigos_iniciales)
            except Exception:
                pass
            xp_ganado = sum(e.nivel * 15 for e in enemigos_iniciales)
            self.jugador.xp += xp_ganado
            print(f"\n¡VICTORIA! Ganas {xp_ganado} XP.")
            
            # Verificar subida de nivel
            while self.jugador.xp >= self.jugador.nivel * XP_POR_NIVEL_BASE:
                self.jugador.subir_nivel()
                nuevas = self._sincronizar_habilidades()
                for hab in nuevas:
                    print(f"¡Has aprendido una nueva habilidad: {hab}!")
            self.verificar_logros()
            return True
        return False

    def evento_aleatorio(self):
        evento = random.choice(["tesoro", "trampa", "mercader", "nada"])
        if evento == "tesoro":
            recompensa = random.randint(20, 50)
            self.jugador.restaurar_vida(recompensa)
            print(f"¡Encuentras un manantial y recuperas {recompensa} puntos de vida!")
        elif evento == "trampa":
            dano = random.randint(10, 30)
            self.jugador.vida -= dano
            print(f"¡Caes en una trampa y pierdes {dano} puntos de vida!")
            if self.jugador.vida <= 0:
                print("La trampa ha sido mortal...")
        elif evento == "mercader":
            print("Te encuentras con un mercader ambulante.")
            costo_pocion = self.jugador.nivel * 10
            opcion = input(f"¿Quieres comprar una 'Poción de Vida' por {costo_pocion} XP? (s/n): ").lower()
            if opcion == 's':
                if self.jugador.xp >= costo_pocion:
                    self.jugador.xp -= costo_pocion
                    self.jugador.inventario["Poción de Vida"] = self.jugador.inventario.get("Poción de Vida", 0) + 1
                    print(f"Compras una Poción de Vida. Tienes {self.jugador.inventario['Poción de Vida']}.")
                else:
                    print("No tienes suficiente XP.")
        elif evento == "nada":
            print("El camino está tranquilo. Continúas tu viaje.")
    
    def iniciar(self):
        print("Bienvenido a Chrono Tactics RPG")
        total_niveles = 10
        while self.nivel_actual <= total_niveles:
            if not self.batalla():
                print("\n--- FIN DEL JUEGO ---")
                break
            
            if self.nivel_actual == total_niveles:
                break

            self.nivel_actual += 1
            self.jugador.restaurar_vida(int(self.jugador.max_vida * 0.25)) # Recupera 25% de vida
            self.jugador.mana = min(self.jugador.max_mana, self.jugador.mana + 20)
            print("\nDescansas y recuperas algo de vida y maná...")
            # Permitir gastar puntos de talento entre niveles
            while self.jugador.puntos_talento > 0:
                print(f"Tienes {self.jugador.puntos_talento} punto(s) de talento.")
                print("Habilidades pasivas disponibles:")
                keys = list(self.jugador.habilidades_pasivas.keys())
                for i, k in enumerate(keys):
                    info = self.jugador.habilidades_pasivas[k]
                    estado = 'Aplicado' if info['aplicado'] else f"Costo {info['costo']}"
                    print(f"{i+1}. {k} - {info['desc']} ({estado})")
                try:
                    elegir = int(input("Elige una para aplicar (0 para saltar): "))
                except ValueError:
                    print("Entrada inválida.")
                    break
                if elegir == 0:
                    break
                if 1 <= elegir <= len(keys):
                    clave = keys[elegir-1]
                    info = self.jugador.habilidades_pasivas[clave]
                    if info['aplicado']:
                        print("Ya has aplicado esta pasiva.")
                        continue
                    if self.jugador.puntos_talento >= info['costo']:
                        self.jugador.puntos_talento -= info['costo']
                        info['aplicado'] = True
                        # aplicar efecto simple
                        if clave == 'Furia':
                            self.jugador.ataque += 2
                        elif clave == 'Coraza':
                            self.jugador.defensa_base += 2
                            self.jugador.defensa += 2
                        print(f"Has desbloqueado {clave}.")
                    else:
                        print("No tienes suficientes puntos.")

            if self.nivel_actual < total_niveles:
                self.evento_aleatorio()
                if self.jugador.vida <= 0:
                    print("\n--- FIN DEL JUEGO ---")
                    break
        
        if self.jugador.vida > 0:
            print("\n¡Felicidades! ¡Has completado todos los niveles de Chrono Tactics!")
            
if __name__ == "__main__":
    juego = None
    archivo_guardado = "progreso_guardado.pkl"
    if os.path.exists(archivo_guardado):
        opcion = input("Se encontró una partida guardada. ¿Deseas cargarla? (s/n): ").lower()
        if opcion == 's':
            juego = Juego.cargar_progreso(archivo_guardado)

    if not juego:
        juego = Juego()
    
    juego.iniciar()