import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, simpledialog, filedialog
import re

def parse_vhdl_entity(vhdl_entity):
    entity_name_match = re.search(r"entity\s+(\w+)\s+is", vhdl_entity, re.IGNORECASE)
    port_matches = re.findall(r"(\w+)\s+:\s+(in|out)\s+(\w+)(\s*\((.*?)\))?;?", vhdl_entity, re.IGNORECASE | re.DOTALL)
    entity_name = entity_name_match.group(1) if entity_name_match else "Unknown"
    ports = []
    for match in port_matches:
        name, direction, type_, _, range_ = match
        ports.append((name, {"direction": direction, "type": type_, "range": range_ or ""}))
    return entity_name, ports

def analyze_vhdl():
    vhdl_content = vhdl_input.get("1.0", tk.END)
    _, ports = parse_vhdl_entity(vhdl_content)
    if not ports:
        messagebox.showerror("Error", "No signal found. Check the VHDL entity.")
    else:
        update_ports_list(ports)

def update_ports_list(ports):
    for i in tree.get_children():
        tree.delete(i)
    for name, info in ports:
        tree.insert("", "end", values=(name, info["direction"], info["type"], info["range"] or "", ""))

def on_flatten_signal():
    selected_item = tree.focus()
    if not selected_item:
        messagebox.showwarning("Warning", "Please select a signal")
        return
    _, _, _, range_, _ = tree.item(selected_item)["values"]
    
    try:
        range_parts = re.findall(r'\d+', range_)
        if len(range_parts) == 2:
            high, low = map(int, range_parts)
            original_size = abs(high - low) + 1
        else:
            messagebox.showerror("Error", "Invalid range format.")
            return
    except Exception as e:
        messagebox.showerror("Error", f"Failed to parse range: {e}")
        return

    num_bits = simpledialog.askinteger("Input", "Number of bits per instance", parent=root)
    if num_bits is None or num_bits <= 0:
        messagebox.showerror("Error", "Invalid number of bits.")
        return

    num_instances = original_size // num_bits
    if original_size % num_bits != 0:
        messagebox.showerror("Error", f"The total bits ({original_size}) is not evenly divisible by {num_bits} bits per instance. Check again if this is what you need.")
        return
    
    tree.set(selected_item, "Flatten", f"{num_instances}x{num_bits}")


def clear_all():
    vhdl_input.delete("1.0", tk.END)
    for i in tree.get_children():
        tree.delete(i)

def generate_wrapper():
    entity_name, _ = parse_vhdl_entity(vhdl_input.get("1.0", tk.END))
    wrapper_entity_name = f"{entity_name}_wrapper"
    wrapper_vhdl = "library ieee;\nuse ieee.std_logic_1164.all;\nuse ieee.std_logic_arith.all;\nuse ieee.std_logic_unsigned.all;\nuse work.latome_hls_pkg.all;\n\n"
    wrapper_vhdl += "entity " + wrapper_entity_name + " is\n    port (\n"
    internal_signals_declaration = ""
    flatten_unflatten_logic_code = ""
    port_map_code = ""
    package_vhdl = "library ieee;\nuse ieee.std_logic_1164.all;\n\npackage latome_hls_pkg is\n"
    custom_types = {}
    for child in tree.get_children():
        name, direction, type_, range_, flatten_option = tree.item(child)["values"]
        if flatten_option:
            num_instances, bits_per_instance = map(int, flatten_option.split('x'))
            custom_type_name = f"array{num_instances}x{bits_per_instance}_t"
            custom_types[custom_type_name] = (num_instances, bits_per_instance)
            wrapper_vhdl += f"        {name} : {direction.upper()} {custom_type_name};\n"
            internal_signal_name = f"{name}_flat"
            std_logic_vector_range = f"std_logic_vector({num_instances*bits_per_instance-1} downto 0)"
            internal_signals_declaration += f"    signal {internal_signal_name}: {std_logic_vector_range};\n"
            if ((direction == "IN") or (direction == 'in')):  # Input signal, flatten                
                flatten_unflatten_logic_code += f"    -- Flatten input signal {name}\n"
                flatten_unflatten_logic_code += f"    gen_{name}_unflatten: for i in 0 to {num_instances-1} generate\n"
                flatten_unflatten_logic_code += f"        {internal_signal_name}((i*{bits_per_instance}) + ({bits_per_instance}-1) downto i*{bits_per_instance}) <= {name}(i)(({bits_per_instance}-1) downto 0);\n"
                flatten_unflatten_logic_code += f"    end generate gen_{name}_unflatten;\n\n"
            elif direction == "OUT":  # Output signal, unflatten
                flatten_unflatten_logic_code += f"    -- Unflatten output signal {name}\n"
                flatten_unflatten_logic_code += f"    gen_{name}_unflatten: for i in 0 to {num_instances-1} generate\n"
                flatten_unflatten_logic_code += f"        {name}(i)(({bits_per_instance}-1) downto 0) <= {internal_signal_name}((i*{bits_per_instance}) + ({bits_per_instance}-1) downto i*{bits_per_instance});\n"
                flatten_unflatten_logic_code += f"    end generate gen_{name}_unflatten;\n\n"           
            port_map_code += f"            {name} => {internal_signal_name},\n"
        else:
            port_definition = f" {type_}({range_})" if range_ else f" {type_}"
            direction = direction.upper()
            wrapper_vhdl += f"        {name} : {direction} {port_definition};\n"
            port_map_code += f"            {name} => {name},\n"
    for custom_type, (instances, bits) in custom_types.items():
        package_vhdl += f"    type {custom_type} is array (0 to {instances-1}) of std_logic_vector({bits-1} downto 0);\n"
    package_vhdl += "end latome_hls_pkg;"
    wrapper_vhdl += "    );\nend " + wrapper_entity_name + ";\n\n"
    wrapper_vhdl += "architecture Behavioral of " + wrapper_entity_name + " is\n"
    wrapper_vhdl += internal_signals_declaration
    wrapper_vhdl += "begin\n" + flatten_unflatten_logic_code
    wrapper_vhdl += "    " + entity_name + "_inst: entity work." + entity_name + "\n        port map (\n"
    wrapper_vhdl += port_map_code.rstrip(',\n') + "\n        );\nend Behavioral;"
    vhdl_output_wrapper.delete("1.0", tk.END)
    vhdl_output_wrapper.insert(tk.INSERT, wrapper_vhdl)
    vhdl_package_def.delete("1.0", tk.END)
    vhdl_package_def.insert(tk.INSERT, package_vhdl)

def show_vhdl_code(vhdl_code):
    code_window = tk.Toplevel(root)
    code_window.title("VHDL Wrapper Code")
    vhdl_code_text = scrolledtext.ScrolledText(code_window, width=100, height=30)
    vhdl_code_text.pack(expand=True, fill='both')
    vhdl_code_text.insert(tk.INSERT, vhdl_code)
    save_button = ttk.Button(code_window, text="Save VHDL File", command=lambda: save_vhdl_file(vhdl_code))
    save_button.pack()

def save_vhdl_file(vhdl_code):
    file_path = filedialog.asksaveasfilename(defaultextension=".vhd",
                                             filetypes=[("VHDL files", "*.vhd;*.vhdl"), ("All Files", "*.*")])
    if file_path:
        with open(file_path, "w") as file:
            file.write(vhdl_code)
        messagebox.showinfo("Success", "The VHDL wrapper code has been saved successfully.")

root = tk.Tk()
root.title("VHDL Wrapper Generator")
root.geometry("800x600") # Set initial window size

# Styling
style = ttk.Style()
style.configure("TButton", font=("Arial", 10), padding=5)
style.configure("TLabel", font=("Arial", 12), padding=5)
style.configure("TFrame", padding=5)
style.configure("Treeview", font=("Arial", 10), rowheight=25)
style.map("Treeview", background=[("selected", "#3498db")])

# Layout
main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill='both', expand=True)

# VHDL Entity Input
input_label_frame = ttk.Frame(main_frame)
input_label_frame.pack(fill='x', expand=False)
vhdl_input_label = ttk.Label(input_label_frame, text="Paste the VHDL entity here:")
vhdl_input_label.pack(side='left')
vhdl_input = scrolledtext.ScrolledText(main_frame, height=10, width=80)
vhdl_input.pack(fill='x', expand=True)

# Action Buttons Frame
action_button_frame = ttk.Frame(main_frame)
action_button_frame.pack(fill='x', expand=False, pady=5)
analyze_button = ttk.Button(action_button_frame, text="Analyze VHDL", command=analyze_vhdl)
analyze_button.pack(side='left', padx=5)
flatten_button = ttk.Button(action_button_frame, text="Flatten Signal", command=on_flatten_signal)
flatten_button.pack(side='left', padx=5)
generate_button = ttk.Button(action_button_frame, text="Generate Wrapper", command=generate_wrapper)
generate_button.pack(side='left', padx=5)
clear_button = ttk.Button(action_button_frame, text="Clear", command=clear_all)
clear_button.pack(side='left', padx=5)

# TreeView for displaying signals
tree_frame = ttk.Frame(main_frame, padding="3")
tree_frame.pack(fill='both', expand=True)
tree = ttk.Treeview(tree_frame, columns=("Name", "Direction", "Type", "Range", "Flatten"), show="headings")
tree.heading("Name", text="Signal Name")
tree.heading("Direction", text="Direction")
tree.heading("Type", text="Type")
tree.heading("Range", text="Range")
tree.heading("Flatten", text="Flatten Options")
tree.pack(fill='both', expand=True)

# Generated VHDL Wrapper Output
vhdl_output_frame = ttk.Frame(main_frame, padding="3")
vhdl_output_frame.pack(fill='both', expand=True)
vhdl_output_wrapper_label = ttk.Label(vhdl_output_frame, text="Generated VHDL Wrapper:")
vhdl_output_wrapper_label.pack()
vhdl_output_wrapper = scrolledtext.ScrolledText(vhdl_output_frame, height=10, width=80)
vhdl_output_wrapper.pack(fill='both', expand=True)

# VHDL Package Definition Output
vhdl_package_def_label = ttk.Label(vhdl_output_frame, text="VHDL Package Definition:")
vhdl_package_def_label.pack()
vhdl_package_def = scrolledtext.ScrolledText(vhdl_output_frame, height=10, width=80)
vhdl_package_def.pack(fill='both', expand=True)

root.mainloop()
