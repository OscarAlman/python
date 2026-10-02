import ctypes as c
import math
import multiprocessing as mp
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================
# CPU TEST
# ============================================================

def stress_cpu(stop):
    value = 0.5

    while not stop.is_set():
        for i in range(20_000):
            value = (
                math.sin(value + i * 0.001) ** 2
                + math.sqrt(value + 1.0)
            )


# ============================================================
# MAC GPU TEST
# ============================================================

def stress_gpu(stop, messages, passes):
    window = None
    context = c.c_void_p()
    pixel_format = c.c_void_p()

    try:
        if sys.platform != "darwin":
            raise RuntimeError("GPU mode requires macOS.")

        gl = c.CDLL(
            "/System/Library/Frameworks/OpenGL.framework/OpenGL"
        )

        def bind(name, result, *arguments):
            function = getattr(gl, name)
            function.restype = result
            function.argtypes = list(arguments)
            return function

        integer = c.c_int
        uint = c.c_uint
        floating = c.c_float
        pointer = c.c_void_p

        choose_format = bind(
            "CGLChoosePixelFormat",
            integer,
            c.POINTER(integer),
            c.POINTER(pointer),
            c.POINTER(integer),
        )

        create_context = bind(
            "CGLCreateContext",
            integer,
            pointer,
            pointer,
            c.POINTER(pointer),
        )

        set_context = bind(
            "CGLSetCurrentContext", integer, pointer
        )

        destroy_context = bind(
            "CGLDestroyContext", integer, pointer
        )

        destroy_format = bind(
            "CGLDestroyPixelFormat", integer, pointer
        )

        # Hardware acceleration, no software fallback,
        # 24-bit colour and 24-bit depth.
        attributes = (integer * 7)(
            73, 72, 8, 24, 12, 24, 0
        )
        format_count = integer()

        error = choose_format(
            attributes,
            c.byref(pixel_format),
            c.byref(format_count),
        )

        if error or not pixel_format.value:
            raise RuntimeError(
                f"Could not select accelerated graphics: {error}"
            )

        error = create_context(
            pixel_format, None, c.byref(context)
        )

        if error or not context.value:
            raise RuntimeError(
                f"Could not create the graphics context: {error}"
            )

        error = set_context(context)

        if error:
            raise RuntimeError(
                f"Could not activate the graphics context: {error}"
            )

        signatures = {
            "glGetString": (c.c_char_p, [uint]),
            "glClearColor": (None, [floating] * 4),
            "glClear": (None, [uint]),
            "glEnable": (None, [uint]),
            "glViewport": (None, [integer] * 4),
            "glMatrixMode": (None, [uint]),
            "glLoadIdentity": (None, []),
            "glFrustum": (None, [c.c_double] * 6),
            "glTranslatef": (None, [floating] * 3),
            "glRotatef": (None, [floating] * 4),
            "glScalef": (None, [floating] * 3),
            "glPushMatrix": (None, []),
            "glPopMatrix": (None, []),
            "glBegin": (None, [uint]),
            "glEnd": (None, []),
            "glVertex3f": (None, [floating] * 3),
            "glColor3f": (None, [floating] * 3),
            "glGenLists": (uint, [integer]),
            "glNewList": (None, [uint, uint]),
            "glEndList": (None, []),
            "glCallList": (None, [uint]),
            "glFinish": (None, []),
            "glPixelStorei": (None, [uint, integer]),
            "glReadBuffer": (None, [uint]),
            "glDrawBuffer": (None, [uint]),
            "glReadPixels": (
                None,
                [
                    integer, integer, integer, integer,
                    uint, uint, pointer,
                ],
            ),
            "glGenFramebuffersEXT": (
                None, [integer, c.POINTER(uint)]
            ),
            "glBindFramebufferEXT": (
                None, [uint, uint]
            ),
            "glGenRenderbuffersEXT": (
                None, [integer, c.POINTER(uint)]
            ),
            "glBindRenderbufferEXT": (
                None, [uint, uint]
            ),
            "glRenderbufferStorageEXT": (
                None, [uint, uint, integer, integer]
            ),
            "glFramebufferRenderbufferEXT": (
                None, [uint, uint, uint, uint]
            ),
            "glCheckFramebufferStatusEXT": (
                uint, [uint]
            ),
        }

        functions = {
            name: bind(name, result, *arguments)
            for name, (result, arguments) in signatures.items()
        }

        def call(name, *arguments):
            return functions[name](*arguments)

        renderer = (
            call("glGetString", 0x1F01) or b"Unknown GPU"
        ).decode(errors="replace")

        messages.put(("gpu", renderer))

        # GPU rendering resolution.
        width, height = 960, 540

        FRAMEBUFFER = 0x8D40
        RENDERBUFFER = 0x8D41
        COLOR_ATTACHMENT = 0x8CE0
        DEPTH_ATTACHMENT = 0x8D00

        framebuffer = uint()
        colour_buffer = uint()
        depth_buffer = uint()

        call(
            "glGenFramebuffersEXT",
            1, c.byref(framebuffer),
        )
        call(
            "glBindFramebufferEXT",
            FRAMEBUFFER, framebuffer.value,
        )

        call(
            "glGenRenderbuffersEXT",
            1, c.byref(colour_buffer),
        )
        call(
            "glBindRenderbufferEXT",
            RENDERBUFFER, colour_buffer.value,
        )
        call(
            "glRenderbufferStorageEXT",
            RENDERBUFFER, 0x8058, width, height,
        )
        call(
            "glFramebufferRenderbufferEXT",
            FRAMEBUFFER,
            COLOR_ATTACHMENT,
            RENDERBUFFER,
            colour_buffer.value,
        )

        call(
            "glGenRenderbuffersEXT",
            1, c.byref(depth_buffer),
        )
        call(
            "glBindRenderbufferEXT",
            RENDERBUFFER, depth_buffer.value,
        )
        call(
            "glRenderbufferStorageEXT",
            RENDERBUFFER, 0x81A6, width, height,
        )
        call(
            "glFramebufferRenderbufferEXT",
            FRAMEBUFFER,
            DEPTH_ATTACHMENT,
            RENDERBUFFER,
            depth_buffer.value,
        )

        call("glDrawBuffer", COLOR_ATTACHMENT)
        call("glReadBuffer", COLOR_ATTACHMENT)

        if (
            call("glCheckFramebufferStatusEXT", FRAMEBUFFER)
            != 0x8CD5
        ):
            raise RuntimeError(
                "Could not create the GPU framebuffer."
            )

        # Generate a detailed 3D torus mathematically.
        mesh = call("glGenLists", 1)

        if not mesh:
            raise RuntimeError("Could not allocate the 3D mesh.")

        call("glNewList", mesh, 0x1300)

        for ring in range(128):
            call("glBegin", 0x0008)

            for segment in range(65):
                v = 2 * math.pi * segment / 64

                for edge in (ring, ring + 1):
                    u = 2 * math.pi * edge / 128

                    radius = 1 + 0.35 * math.cos(v)
                    shade = 0.5 + 0.5 * math.cos(v)

                    call(
                        "glColor3f",
                        0.15 + 0.8 * shade,
                        0.3 + 0.5 * math.sin(u) ** 2,
                        0.85,
                    )

                    call(
                        "glVertex3f",
                        radius * math.cos(u),
                        radius * math.sin(u),
                        0.35 * math.sin(v),
                    )

            call("glEnd")

        call("glEndList")
        call("glEnable", 0x0B71)
        call("glClearColor", 0.015, 0.025, 0.05, 1.0)
        call("glViewport", 0, 0, width, height)

        call("glMatrixMode", 0x1701)
        call("glLoadIdentity")

        aspect = width / height
        call("glFrustum", -aspect, aspect, -1, 1, 1, 100)

        # Tkinter displays previews of the GPU-rendered image.
        window = tk.Tk()
        window.title("GPU rendering — Escape to stop")
        window.resizable(False, False)

        preview = tk.Label(window, borderwidth=0)
        preview.pack()

        window.bind("<Escape>", lambda event: stop.set())
        window.protocol("WM_DELETE_WINDOW", stop.set)

        pixels = (c.c_ubyte * (width * height * 3))()
        call("glPixelStorei", 0x0D05, 1)

        header = f"P6\n{width} {height}\n255\n".encode()

        image = tk.PhotoImage(
            master=window,
            data=header + bytes(width * height * 3),
            format="PPM",
        )
        preview.configure(image=image)

        started = time.perf_counter()
        last_report = started
        last_preview = started
        frames = 0

        while not stop.is_set():
            window.update()

            if stop.is_set():
                break

            elapsed = time.perf_counter() - started

            # Repeatedly redraw the scene to increase GPU work.
            for _ in range(passes):
                if stop.is_set():
                    break

                call("glClear", 0x4100)
                call("glMatrixMode", 0x1700)
                call("glLoadIdentity")
                call("glTranslatef", 0, 0, -12)

                for row in range(5):
                    for column in range(7):
                        call("glPushMatrix")

                        call(
                            "glTranslatef",
                            (column - 3) * 2.1,
                            (row - 2) * 2.1,
                            0,
                        )

                        call(
                            "glRotatef",
                            elapsed * 40 + row * 17 + column * 11,
                            1, 0.7, 0.3,
                        )

                        call("glScalef", 0.7, 0.7, 0.7)
                        call("glCallList", mesh)
                        call("glPopMatrix")

            call("glFinish")
            frames += 1
            now = time.perf_counter()

            # Preview updates at up to 20 FPS.
            # Rendering continues between preview updates.
            if now - last_preview >= 0.05:
                call(
                    "glReadPixels",
                    0, 0, width, height,
                    0x1907, 0x1401, pixels,
                )

                raw = bytes(pixels)
                stride = width * 3

                flipped = b"".join(
                    raw[y * stride:(y + 1) * stride]
                    for y in range(height - 1, -1, -1)
                )

                image.configure(
                    data=header + flipped,
                    format="PPM",
                )

                last_preview = now

            if now - last_report >= 1:
                fps = frames / (now - last_report)

                messages.put(("fps", fps))

                window.title(
                    f"{renderer} | {fps:.1f} render FPS | "
                    "Escape to stop"
                )

                frames = 0
                last_report = now

    except Exception as error:
        messages.put(("error", str(error)))

    finally:
        stop.set()

        if context.value:
            set_context(None)
            destroy_context(context)

        if pixel_format.value:
            destroy_format(pixel_format)

        if window is not None:
            window.destroy()


# ============================================================
# TKINTER CONTROL PANEL
# ============================================================

def main():
    root = tk.Tk()
    root.title("Mac CPU and GPU Stress Test")
    root.geometry("560x460")

    panel = ttk.Frame(root, padding=20)
    panel.pack(fill="both", expand=True)

    ttk.Label(
        panel,
        text="Mac CPU and GPU Stress Test",
        font=("Helvetica", 19, "bold"),
    ).pack(anchor="w", pady=(0, 15))

    cpu_enabled = tk.BooleanVar(value=True)
    gpu_enabled = tk.BooleanVar(value=True)

    ttk.Checkbutton(
        panel,
        text="Stress CPU using multiprocessing",
        variable=cpu_enabled,
    ).pack(anchor="w")

    ttk.Checkbutton(
        panel,
        text="Stress GPU with animated 3D rendering",
        variable=gpu_enabled,
    ).pack(anchor="w")

    logical_cores = os.cpu_count() or 1

    workers = tk.StringVar(
        value=str(max(1, logical_cores - 1))
    )
    seconds = tk.StringVar(value="60")
    passes = tk.StringVar(value="8")

    settings = ttk.Frame(panel)
    settings.pack(fill="x", pady=15)

    fields = [
        ("CPU processes", workers),
        ("Duration in seconds", seconds),
        ("GPU render passes: 1–64", passes),
    ]

    for row, (label, variable) in enumerate(fields):
        ttk.Label(settings, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=4,
        )

        ttk.Entry(
            settings,
            textvariable=variable,
            width=12,
        ).grid(
            row=row,
            column=1,
            padx=20,
        )

    gpu_info = tk.StringVar(value="GPU: not started")
    status = tk.StringVar(value="Ready")

    ttk.Label(
        panel,
        textvariable=gpu_info,
        wraplength=510,
    ).pack(anchor="w", pady=5)

    ttk.Label(
        panel,
        textvariable=status,
        wraplength=510,
    ).pack(anchor="w", pady=5)

    progress = ttk.Progressbar(panel, maximum=100)
    progress.pack(fill="x", pady=10)

    ttk.Label(
        panel,
        text=(
            "Monitor temperatures separately; no thermal cutoff.\n"
            "FPS describes this workload, not a standard benchmark."
        ),
        wraplength=510,
    ).pack(anchor="w", pady=10)

    controls = ttk.Frame(panel)
    controls.pack(anchor="w")

    # Spawn avoids inheriting Tkinter state into child processes.
    process_context = mp.get_context("spawn")

    processes = []
    stop_event = None
    messages = None

    start_time = 0
    duration = 0
    stop_deadline = None
    closing = False
    failure = None
    last_fps = None

    def stop_test():
        nonlocal stop_deadline

        if stop_event is not None:
            stop_event.set()

            if stop_deadline is None:
                stop_deadline = time.monotonic() + 3

            stop_button.config(state="disabled")

    def read_messages():
        nonlocal failure, last_fps

        if messages is None:
            return

        try:
            while True:
                kind, value = messages.get_nowait()

                if kind == "gpu":
                    gpu_info.set("GPU: " + value)

                elif kind == "fps":
                    last_fps = value

                elif kind == "error":
                    failure = value
                    stop_test()

        except queue.Empty:
            pass

    def start_test():
        nonlocal processes, stop_event, messages
        nonlocal start_time, duration, stop_deadline
        nonlocal failure, last_fps

        try:
            if not cpu_enabled.get() and not gpu_enabled.get():
                raise ValueError("Select CPU, GPU, or both.")

            duration = int(seconds.get())

            count = (
                int(workers.get())
                if cpu_enabled.get()
                else 1
            )

            repeats = (
                int(passes.get())
                if gpu_enabled.get()
                else 1
            )

            if not 1 <= duration <= 86400:
                raise ValueError(
                    "Duration must be between 1 and 86400 seconds."
                )

            if not 1 <= count <= logical_cores:
                raise ValueError(
                    f"CPU processes must be between "
                    f"1 and {logical_cores}."
                )

            if not 1 <= repeats <= 64:
                raise ValueError(
                    "GPU render passes must be between 1 and 64."
                )

            if gpu_enabled.get() and sys.platform != "darwin":
                raise ValueError(
                    "This version's GPU mode requires macOS."
                )

        except ValueError as error:
            messagebox.showerror("Settings", str(error))
            return

        stop_event = process_context.Event()
        messages = process_context.Queue()

        stop_deadline = None
        failure = None
        last_fps = None
        processes = []

        if cpu_enabled.get():
            for index in range(count):
                processes.append(
                    process_context.Process(
                        target=stress_cpu,
                        args=(stop_event,),
                        name=f"CPU {index + 1}",
                    )
                )

        if gpu_enabled.get():
            processes.append(
                process_context.Process(
                    target=stress_gpu,
                    args=(stop_event, messages, repeats),
                    name="GPU",
                )
            )

        gpu_info.set(
            "GPU: starting..."
            if gpu_enabled.get()
            else "GPU: disabled"
        )

        progress["value"] = 0
        start_time = time.monotonic()

        start_button.config(state="disabled")
        stop_button.config(state="normal")

        try:
            for process in processes:
                process.start()

        except Exception as error:
            failure = f"Could not start: {error}"
            stop_test()

    def poll():
        nonlocal processes, stop_event, messages, failure

        read_messages()

        if processes:
            elapsed = time.monotonic() - start_time

            for process in processes:
                if (
                    process.pid is not None
                    and process.exitcode not in (None, 0)
                    and stop_deadline is None
                ):
                    failure = (
                        f"{process.name} exited unexpectedly "
                        f"(code {process.exitcode})."
                    )
                    stop_test()

            if elapsed >= duration or stop_event.is_set():
                stop_test()

            progress["value"] = min(
                100, elapsed / duration * 100
            )

            if failure:
                status.set("Error: " + failure)

            elif stop_deadline is not None:
                status.set("Stopping...")

            else:
                text = (
                    f"Running: {elapsed:.0f} / "
                    f"{duration} seconds"
                )

                if last_fps is not None:
                    text += f" | {last_fps:.1f} render FPS"

                status.set(text)

            if (
                stop_deadline is not None
                and time.monotonic() >= stop_deadline
            ):
                for process in processes:
                    if (
                        process.pid is not None
                        and process.is_alive()
                    ):
                        process.terminate()
                        if failure is None:
                            failure = (
                                "A worker did not stop promptly "
                                "and was terminated."
                            )

            finished = all(
                process.pid is None or not process.is_alive()
                for process in processes
            )

            if finished:
                for process in processes:
                    if process.pid is not None:
                        process.join(timeout=0)

                # Collect any final error sent before worker exit.
                read_messages()

                processes = []
                stop_event = None

                if messages is not None:
                    messages.close()
                    messages = None

                start_button.config(state="normal")
                stop_button.config(state="disabled")

                if failure:
                    status.set("Error: " + failure)
                else:
                    status.set(
                        "Test stopped. Completion does not "
                        "certify hardware stability."
                    )

        if closing and not processes:
            root.destroy()
            return

        root.after(100, poll)

    def close():
        nonlocal closing

        closing = True
        stop_test()

        if not processes:
            root.destroy()

    start_button = ttk.Button(
        controls,
        text="Start",
        command=start_test,
    )
    start_button.pack(side="left")

    stop_button = ttk.Button(
        controls,
        text="Stop",
        command=stop_test,
        state="disabled",
    )
    stop_button.pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    root.mainloop()


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":
    mp.freeze_support()
    main()