import math
import pygame

BG = (11, 18, 29)
PANEL = (18, 29, 44)
LINE = (36, 53, 72)
INK = (229, 238, 249)
MUTED = (132, 154, 177)
TEAL = (74, 220, 187)
AMBER = (248, 187, 101)
RED = (248, 112, 133)

# label, config group, parameter, keyboard increment, slider minimum, slider maximum
FIELDS = [
    ("Balance Kp", "balance", "kp", 50, 0, 20000),
    ("Balance Ki", "balance", "ki", 10, 0, 500),
    ("Balance Kd", "balance", "kd", 10, 0, 1000),
    ("Velocity Kp", "velocity", "kp", .005, 0, .3),
    ("Velocity Ki", "velocity", "ki", .002, 0, .1),
    ("Velocity Kd", "velocity", "kd", .005, 0, .1),
    ("Mass / kg", "robot", "mass", 1, 10, 100),
    ("COM height / m", "robot", "height", .05, .3, 1.5),
    ("Gravity / m/s2", "robot", "gravity", .1, 1, 20),
    ("Torque limit / Nm", "robot", "torque_limit", 5, 10, 300),
    ("Fall angle / deg", "robot", "fall_angle_deg", 1, 10, 75),
    ("Initial lean / deg", "simulation", "initial_angle_deg", 1, -30, 30),
    ("Lean limit / deg", "simulation", "lean_limit_deg", 1, 1, 30),
    ("Command / m/s", "simulation", "command_speed", .1, .1, 3),
    ("Push force / N", "disturbance", "force", 10, 0, 1000),
    ("Push duration / s", "disturbance", "duration", .05, .05, 1),
    ("Run duration / s", "simulation", "duration", 5, 5, 120),
    ("Physics dt / s", "simulation", "dt", .001, .001, .02),
]

FIELD_HELP = [
    "Main balance correction. Higher Kp reacts harder to lean error, but too much can cause violent oscillation and torque saturation.",
    "Accumulates persistent lean error. Ki removes steady bias, but too much builds up and can cause slow overshoot after a push.",
    "Damps angular motion. Higher Kd usually reduces swinging; too much makes the controller resist motion aggressively.",
    "Turns velocity error into a lean request. Higher values accelerate and brake harder, increasing balance demand.",
    "Removes persistent speed error. Too much can keep requesting lean after the target has changed and cause overshoot.",
    "Damps rapid changes in velocity. It can smooth tracking, but high values may make speed response sluggish or noisy.",
    "Body mass sets inertia. A heavier robot needs more torque and is harder to recover with the same actuator limit.",
    "Height of the centre of mass. A taller robot falls more slowly but gravity produces a larger overturning torque.",
    "Gravity destabilises the upright robot. Raising it makes falls and recovery demands grow more quickly.",
    "Maximum available actuator torque. Lower limits expose saturation and make large disturbances harder to recover from.",
    "Lean angle that counts as a fall. A smaller boundary ends experiments sooner; a larger one allows deeper recovery attempts.",
    "Lean at the start of each run. Larger offsets immediately test whether the controller can capture the robot.",
    "Maximum lean the velocity loop may request. More lean gives stronger acceleration but leaves less balance margin.",
    "Speed requested while holding W or S. Faster targets demand more lean, torque and braking effort.",
    "Strength of each Space-bar push. Increase it to find the controller's disturbance-recovery limit.",
    "How long each push acts. Longer pulses transfer more momentum and are usually harder to reject than short pushes.",
    "Maximum simulated time for a run. Longer runs reveal slow drift and give the robot more time to settle.",
    "Physics integration interval. Smaller values are more accurate but require more computation; large values can distort stability.",
]

VISIBLE_FIELDS = 8
SLIDER_X = 838
SLIDER_WIDTH = 352
CONTINUE_RECT = pygame.Rect(724, 731, 276, 42)
EXIT_RECT = pygame.Rect(1018, 731, 174, 42)


def field_window_start(selected):
    # Page the list in stable blocks so clicking a lower slider does not make
    # that slider jump vertically beneath the pointer.
    return min((selected // VISIBLE_FIELDS) * VISIBLE_FIELDS,
               len(FIELDS) - VISIBLE_FIELDS)


def slider_rect(index, selected):
    start = field_window_start(selected)
    if not start <= index < start + VISIBLE_FIELDS:
        return None
    row = index - start
    return pygame.Rect(SLIDER_X, 197 + row * 34, SLIDER_WIDTH, 14)


def field_rect(index, selected):
    start = field_window_start(selected)
    if not start <= index < start + VISIBLE_FIELDS:
        return None
    return pygame.Rect(828, 172 + (index-start) * 34, 373, 35)


def field_at_position(position, selected):
    for index in range(len(FIELDS)):
        rect = field_rect(index, selected)
        if rect and rect.collidepoint(position):
            return index
    return None


class Renderer:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1240, 820))
        pygame.display.set_caption("Planar / Balance Lab")
        self.fonts = {size: pygame.font.SysFont("consolas", size) for size in (12, 14, 16, 18, 22, 28, 36)}

    def text(self, value, pos, size=16, color=INK):
        self.screen.blit(self.fonts[size].render(str(value), True, color), pos)

    def panel(self, rect):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=12)
        pygame.draw.rect(self.screen, LINE, rect, 1, border_radius=12)

    def button(self, text, rect, primary=False):
        color = TEAL if primary else LINE
        pygame.draw.rect(self.screen, color, rect, border_radius=7)
        self.text(text, (rect[0]+14, rect[1]+12), 16, BG if primary else INK)

    def wrapped_text(self, value, pos, width, size=14, color=MUTED, line_height=None):
        font = self.fonts[size]
        line_height = line_height or size + 6
        words, lines, current = value.split(), [], ""
        for word in words:
            candidate = word if not current else current + " " + word
            if font.size(candidate)[0] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        for index,line in enumerate(lines):
            self.text(line,(pos[0],pos[1]+index*line_height),size,color)
        return len(lines)

    def history_chart(self, rect, rows, key, target, label, unit, floor, scale=1):
        x,y,w,h = rect
        self.panel(rect)
        self.text(label.upper(),(x+18,y+14),14,MUTED)
        if not rows:
            self.text("No samples recorded",(x+18,y+54),16,AMBER)
            return
        self.text(f"actual {rows[-1][key]*scale:+.2f} {unit}",(x+18,y+38),16,INK)
        plot_top, plot_bottom = y+70, y+h-18
        middle = (plot_top+plot_bottom)/2
        limit = max(floor,max(abs(row[name]*scale) for row in rows for name in (key,target)))*1.1
        pygame.draw.line(self.screen,LINE,(x+18,middle),(x+w-18,middle),1)
        stride = max(1,math.ceil(len(rows)/(w-36)))
        sampled = rows[::stride]
        if sampled[-1] is not rows[-1]:
            sampled.append(rows[-1])
        for field,color in ((target,AMBER),(key,TEAL)):
            points = [(x+18+i*(w-36)/max(1,len(sampled)-1),
                       middle-row[field]*scale/limit*(plot_bottom-plot_top)/2)
                      for i,row in enumerate(sampled)]
            if len(points)>1:
                pygame.draw.lines(self.screen,color,False,points,2)

    def spark(self, rect, rows, key, target, label, unit, floor):
        x, y, w, h = rect
        self.panel(rect)
        self.text(label.upper(), (x+18, y+12), 14, MUTED)
        value = rows[-1][key] if rows else 0
        scale = 180/math.pi if key == "angle" else 1
        self.text(f"{value*scale:+.2f} {unit}", (x+18, y+36), 22)
        if not rows:
            return
        recent = rows[-600:]
        limit = max(floor, max(abs(r[k]*scale) for r in recent for k in (key, target))) * 1.15
        mid, amplitude = y+h-47, 28
        pygame.draw.line(self.screen, LINE, (x+18, mid), (x+w-18, mid))
        for field, color in ((target, AMBER), (key, TEAL)):
            points = [(x+18+i*(w-36)/max(1,len(recent)-1), mid-r[field]*scale/limit*amplitude)
                      for i, r in enumerate(recent)]
            if len(points) > 1:
                pygame.draw.lines(self.screen, color, False, points, 2)

    def robot(self, env, rect):
        x, y, w, h = rect
        self.panel(rect)
        self.text("SAGITTAL PLANE", (x+20, y+18), 14, MUTED)
        self.text("COM + lean / translating support", (x+20, y+41), 12, MUTED)
        ground = y+h-68
        cx, cy = x+w*.5, ground-10
        scale = 165
        # Camera follows x, but the ground ruler moves in world coordinates.
        for i in range(-6, 7):
            mark = cx + i*100 - (env.state.x*100)%100
            if x+15 < mark < x+w-15:
                pygame.draw.line(self.screen, LINE, (mark, y+85), (mark, ground+10), 1)
                self.text(f"{math.floor(env.state.x)+i}m", (mark-9,ground+21), 12, MUTED)
        for yy in range(y+100, int(ground), 50):
            pygame.draw.line(self.screen, (25,39,56), (x+15,yy), (x+w-15,yy))
        pygame.draw.line(self.screen, MUTED, (x+16,ground),(x+w-16,ground), 2)
        theta = env.state.theta
        height_scale = max(.5, min(1.35, env.config["robot"]["height"]/.8))
        def point(side, up, angle=theta):
            return (int(cx + height_scale*(side*math.cos(angle) + up*math.sin(angle))),
                    int(cy + height_scale*(side*math.sin(angle) - up*math.cos(angle))))
        color = RED if env.fell else TEAL
        target = env.last["desired_angle"] if env.last else 0
        pygame.draw.line(self.screen, AMBER, point(0,0), point(0,240,target), 1)
        for yy in range(int(cy-245*height_scale), int(cy), 12):
            pygame.draw.line(self.screen, LINE, (cx,yy),(cx,yy+5),1)
        # Decorative limbs are rigid in the body frame; no invented walking gait.
        for a,b in [((-33,0),(-24,63)), ((-24,63),(0,102)), ((33,0),(24,63)),
                    ((24,63),(0,102)), ((0,102),(0,185)), ((-48,120),(-29,165)),
                    ((-29,165),(0,185)), ((48,120),(29,165)), ((29,165),(0,185))]:
            pygame.draw.line(self.screen, color, point(*a), point(*b), 7)
        for joint in [(0,102),(-24,63),(24,63),(0,185)]:
            pygame.draw.circle(self.screen, INK, point(*joint), 5)
        pygame.draw.circle(self.screen, color, point(0,218), int(21*height_scale), 3)
        pygame.draw.line(self.screen, color, point(0,185),point(0,197), 5)
        for side in (-33,33):
            pygame.draw.line(self.screen, INK, point(side-10,0),point(side+10,0),5)
        com = point(0,165)
        pygame.draw.circle(self.screen, AMBER, com, 7)
        pygame.draw.circle(self.screen, BG, com, 3)
        self.text("COM", (com[0]+14,com[1]-8),12,AMBER)
        pygame.draw.line(self.screen, AMBER, (com[0],com[1]+10),(com[0],ground),1)
        force = env.last["disturbance_force"] if env.last else 0
        if force:
            direction = 1 if force > 0 else -1
            tip = (com[0]-direction*35, com[1])
            tail = (tip[0]-direction*95, tip[1])
            pygame.draw.line(self.screen, RED, tail, tip, 5)
            pygame.draw.polygon(self.screen, RED, [tip,(tip[0]-direction*15,tip[1]-9),(tip[0]-direction*15,tip[1]+9)])
            self.text(f"{force:+.0f} N", (min(tip[0],tail[0]),tip[1]-30),16,RED)
        self.text(f"x {env.state.x:+.2f} m", (x+20,y+h-30),14,MUTED)
        self.text(f"t {env.time:06.2f} s", (x+w-150,y+h-30),14,TEAL)

    def draw(self, app):
        self.screen.fill(BG)
        self.text("PLANAR /", (28,20),28,TEAL)
        self.text("BALANCE LAB", (182,20),28)
        self.text("01   CONTROL SYSTEMS / INVERTED PENDULUM",(30,58),12,MUTED)
        if app.analysis_view:
            self.text("RUN ANALYSIS",(966,30),18,TEAL)
            self.analysis_dashboard(app)
            pygame.display.flip()
            return
        status = "PAUSED" if app.paused else "LIVE" if app.running else "EXPERIMENT SETUP"
        self.text(status, (930,30),18, AMBER if app.paused else TEAL)
        self.robot(app.env,(28,96,770,434))
        rows = app.logger.rows if app.logger else app.previous_rows
        self.spark((28,546,246,150),rows,"angle","desired_angle","Body lean","deg",3)
        self.spark((290,546,246,150),rows,"velocity","desired_velocity","Velocity","m/s",1)
        self.spark((552,546,246,150),rows,"actual_torque","commanded_torque","Torque","Nm",80)
        self.panel((816,96,396,600))
        self.text("EXPERIMENT / "+app.scenario.upper(), (836,114),18)
        self.text("PID > lean > torque > plant",(836,145),14,MUTED)
        if app.running:
            self.live_sidebar(app)
        else:
            self.tuning_sidebar(app)
        self.panel((28,712,1184,80))
        if app.running:
            self.text("W  forward    S  backward    release  brake    SPACE  push",(48,728),16)
            self.text("P  pause      R  save + reset      ESC  finish + analyse",(48,757),14,MUTED)
            self.button("FINISH / ESC", (1020,731,172,42))
        else:
            self.text("1-6  preset    UP/DOWN  select    LEFT/RIGHT  adjust    E  type value",(48,728),14)
            self.text("ENTER  run    TAB  balance/tracking mode    Q / ESC  quit",(48,757),14,MUTED)
            self.button("START / ENTER", (1020,731,172,42),True)
        if app.message:
            self.text(app.message[:110], (32,800),12, AMBER)
        pygame.display.flip()

    def analysis_dashboard(self, app):
        summary,rows = app.summary or {},app.previous_rows
        status = summary.get("status","no_data").upper()
        status_color = RED if status == "FELL" else TEAL if status == "STABLE" else AMBER
        self.history_chart((28,96,770,184),rows,"angle","desired_angle","Body lean history","deg",3,180/math.pi)
        self.history_chart((28,294,770,184),rows,"velocity","desired_velocity","Velocity tracking","m/s",1)
        self.history_chart((28,492,770,204),rows,"actual_torque","commanded_torque","Actuator torque","Nm",80)
        self.panel((816,96,396,600))
        self.text("EXPERIMENT RESULT",(836,116),14,MUTED)
        self.text(status,(836,143),28,status_color)
        self.text(summary.get("termination_reason","unknown").replace("_"," ").upper(),(836,179),12,MUTED)
        metrics = [
            ("Duration",summary.get("duration_s",0),"s"),
            ("Peak lean",summary.get("max_lean_deg",0),"deg"),
            ("Angle error RMS",summary.get("rms_angle_error_deg",0),"deg"),
            ("Velocity RMSE",summary.get("velocity_rmse_m_s",0),"m/s"),
            ("Peak torque",summary.get("peak_torque_Nm",0),"Nm"),
            ("Torque saturation",summary.get("saturation_percent",0),"%"),
            ("Peak disturbance",summary.get("peak_disturbance_N",0),"N"),
        ]
        for index,(label,value,unit) in enumerate(metrics):
            yy=218+index*33
            self.text(label,(836,yy),14,MUTED)
            self.text(f"{value:.2f} {unit}",(1055,yy),14,INK)
        events = summary.get("disturbance_events",[])
        observed = [event.get("recovery_after_push_s") for event in events
                    if event.get("recovery_after_push_s") is not None]
        recovery = f"{max(observed):.2f} s" if observed else "not observed"
        self.text("Measured recovery",(836,452),14,MUTED)
        self.text(recovery,(1055,452),14,INK)
        pygame.draw.line(self.screen,LINE,(836,480),(1190,480))
        self.text("WHAT THIS RUN SHOWS",(836,499),14,TEAL)
        if status == "FELL":
            insight = "The fall boundary was crossed. Try less disturbance, more torque authority, or retune damping before rerunning."
        elif summary.get("saturation_percent",0) >= 20:
            insight = "The robot stayed up, but the actuator spent substantial time at its limit. The controller is demanding torque the plant cannot supply."
        elif status == "STABLE":
            insight = "The robot finished inside the balance and velocity tolerances. Increase the push or alter one gain to explore its recovery margin."
        else:
            insight = "The robot did not fall, but it was not settled during the final observation window. Inspect oscillation and tracking error before retuning."
        self.wrapped_text(insight,(836,527),350,14,MUTED,20)
        if app.last_run_directory:
            self.text("Saved in "+app.last_run_directory.name,(836,661),12,MUTED)
        self.panel((28,712,1184,80))
        self.text("Review the response, then change one variable and run again.",(48,728),14,MUTED)
        self.text("ENTER / C  continue testing",(48,757),14,TEAL)
        self.button("CONTINUE TESTING",CONTINUE_RECT,True)
        self.button("EXIT",EXIT_RECT)

    def live_sidebar(self, app):
        env = app.env
        row = env.last or {}
        values = [("Target velocity",f"{env.desired_velocity:+.2f} m/s"),
                  ("Actual velocity",f"{env.state.velocity:+.2f} m/s"),
                  ("Body lean",f"{math.degrees(env.state.theta):+.2f} deg"),
                  ("Target lean",f"{math.degrees(row.get('desired_angle',0)):+.2f} deg"),
                  ("Angular velocity",f"{math.degrees(env.state.omega):+.1f} deg/s"),
                  ("Motor torque",f"{row.get('actual_torque',0):+.1f} Nm")]
        for i,(label,value) in enumerate(values):
            yy = 185+i*49
            self.text(label,(836,yy),14,MUTED)
            self.text(value,(1040,yy),16)
        limit = env.config["robot"]["torque_limit"]
        usage = min(1.,abs(row.get("actual_torque",0))/limit)
        pygame.draw.rect(self.screen,LINE,(836,490,354,8),border_radius=4)
        pygame.draw.rect(self.screen,RED if env.saturated else TEAL,(836,490,354*usage,8),border_radius=4)
        self.text("SATURATED" if env.saturated else "ACTUATOR HEADROOM",(836,512),14,RED if env.saturated else MUTED)
        self.text(f"Limit +/- {limit:g} Nm  |  Fall {env.config['robot']['fall_angle_deg']:g} deg",(836,543),14,MUTED)
        self.text(f"Mode: {app.mode.upper()}",(836,593),18,TEAL)
        self.text("CSV recording / fixed physics step",(836,629),14,MUTED)
        self.text("Teal = actual   Amber = requested",(836,656),12,MUTED)

    def tuning_sidebar(self, app):
        start = field_window_start(app.selected)
        for i,field in enumerate(FIELDS[start:start+VISIBLE_FIELDS]):
            label,group,key,_,minimum,maximum = field
            yy = 177+i*34
            selected = start+i == app.selected
            if selected:
                pygame.draw.rect(self.screen,(27,43,61),(828,yy-5,373,35),border_radius=5)
            self.text(label,(838,yy),14,INK if selected else MUTED)
            value = app.edit_text+"_" if selected and app.editing else f"{app.config[group][key]:g}"
            self.text(value,(1100,yy),14,TEAL if selected else INK)
            track = slider_rect(start+i, app.selected)
            current = app.config[group][key]
            ratio = max(0., min(1., (current-minimum)/(maximum-minimum)))
            pygame.draw.line(self.screen,LINE,(track.left,track.centery),(track.right,track.centery),4)
            pygame.draw.line(self.screen,TEAL,(track.left,track.centery),
                             (track.left+round(track.width*ratio),track.centery),4)
            pygame.draw.circle(self.screen,TEAL if selected else MUTED,
                               (track.left+round(track.width*ratio),track.centery),5)
        self.text(f"PARAMETER {app.selected+1:02d}/{len(FIELDS)}  |  DRAG TO TUNE  |  {app.mode.upper()}",
                  (836,458),12,TEAL)
        pygame.draw.line(self.screen,LINE,(836,481),(1190,481))
        if app.hovered_field is not None:
            label,_,_,_,minimum,maximum = FIELDS[app.hovered_field]
            self.text("ABOUT / "+label.upper(),(836,498),16,TEAL)
            self.text(f"Slider range {minimum:g} to {maximum:g}",(836,526),12,AMBER)
            self.wrapped_text(FIELD_HELP[app.hovered_field],(836,554),350,14,MUTED,21)
        elif app.summary:
            s = app.summary
            self.text("PREVIOUS / "+s["status"].upper(),(836,498),18,RED if s["status"]=="fell" else TEAL)
            for i,(label,key,unit) in enumerate([("Angle RMS","rms_angle_error_deg","deg"),
                    ("Velocity RMSE","velocity_rmse_m_s","m/s"),
                    ("Saturation","saturation_percent","%"), ("Duration","duration_s","s")]):
                self.text(label,(836,532+i*30),14,MUTED)
                self.text(f"{s.get(key,0):.2f} {unit}",(1060,532+i*30),14)
        else:
            self.text("COMPARISON PRESETS",(836,498),16,TEAL)
            for i,label in enumerate(["1 PID recovery   2 No controller", "3 P only         4 Excessive gain",
                                       "5 Large push     6 Tracking"]):
                self.text(label,(836,537+i*28),14,MUTED)
            self.text("Tune, run, push, inspect, repeat.",(836,645),14,AMBER)
            self.text("SPACE applies the configured push.",(836,670),12,MUTED)
