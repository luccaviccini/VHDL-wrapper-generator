import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, simpledialog, filedialog
import re

def parse_vhdl_entity(vhdl_entity):
    entity_name_match = re.search(r"entity\s+(\w+)\s+is", vhdl_entity, re.IGNORECASE)
    # Adjust the regex to optionally match signals without a specified range.
    port_matches = re.findall(r"(\w+)\s+:\s+(in|out)\s+(\w+)(\s*\((.*?)\))?;?", vhdl_entity, re.IGNORECASE | re.DOTALL)

    entity_name = entity_name_match.group(1) if entity_name_match else "Unknown"
    ports = []
    for match in port_matches:
        name, direction, type_, _, range_ = match  # Adjusted to capture optional range
        # No need to separate type and range here, as it's already done by the adjusted regex
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
    selected_item = tree.focus()  # Retorna o item selecionado na Treeview
    if not selected_item:
        messagebox.showwarning("Warning", "Please select a signal")
        return
    num_instances = simpledialog.askinteger("Input", "Number of instances:", parent=root)
    if num_instances is None:
        return
    num_bits = simpledialog.askinteger("Input", "Number of bits per instance", parent=root)
    if num_bits is None:
        return
    tree.set(selected_item, "Flatten", f"{num_instances}x{num_bits}")

def clear_all():
    vhdl_input.delete("1.0", tk.END)  # Limpa a caixa de texto de entrada
    for i in tree.get_children():
        tree.delete(i)  # Limpa todos os itens na Treeview

def generate_wrapper():
    entity_name, _ = parse_vhdl_entity(vhdl_input.get("1.0", tk.END))
    wrapper_entity_name = f"{entity_name}_wrapper"

    # Start defining the wrapper entity and port list
    wrapper_vhdl = f"entity {wrapper_entity_name} is\n"
    wrapper_vhdl += "    port (\n"

    # Declarations for internal signals and logic
    internal_signals_declaration = ""
    flatten_unflatten_logic_code = ""
    port_map_code = ""

    for child in tree.get_children():
        name, direction, type_, range_, flatten_option = tree.item(child)["values"]
        print(direction, flatten_option)
        # Port definitions remain unchanged
        port_definition = f" {type_}({range_})" if range_ != "N/A" else f" {type_}"
        direction = direction.upper()
        wrapper_vhdl += f"        {name} : {direction}{port_definition};\n"

        # Differentiating between input and output signals
        if flatten_option:
            num_instances, bits_per_instance = map(int, flatten_option.split('x'))
            total_bits = num_instances * bits_per_instance - 1
            internal_signal_name = f"{name}_flat"
            internal_signals_declaration += f"    signal {internal_signal_name}: std_logic_vector({total_bits} downto 0);\n"
            
            if ((direction == "IN") or (direction == 'in')):  # Input signal, flatten                
                flatten_unflatten_logic_code += f"    -- Flatten input signal {name}\n"
                flatten_unflatten_logic_code += f"    {name}_flat: for i in 0 to {num_instances-1} generate\n"
                flatten_unflatten_logic_code += f"        {internal_signal_name}((i*{bits_per_instance}) + {bits_per_instance}-1 downto i*{bits_per_instance}) <= {name}(i)({bits_per_instance}-1 downto 0);\n"
                flatten_unflatten_logic_code += f"    end generate gen_{name}_flatten;\n\n"
            elif direction == "OUT":  # Output signal, unflatten
                flatten_unflatten_logic_code += f"    -- Unflatten output signal {name}\n"
                flatten_unflatten_logic_code += f"    {name}_flat: for i in 0 to {num_instances-1} generate\n"
                flatten_unflatten_logic_code += f"        {name}(i)({bits_per_instance}-1 downto 0) <= {internal_signal_name}((i*{bits_per_instance}) + {bits_per_instance}-1 downto i*{bits_per_instance});\n"
                flatten_unflatten_logic_code += f"    end generate gen_{name}_unflatten;\n\n"

            port_map_code += f"            {name} => {internal_signal_name},\n"
        else:
            port_map_code += f"            {name} => {name},\n"


    # Finish port definitions
    wrapper_vhdl += "    );\n"
    wrapper_vhdl += f"end {wrapper_entity_name};\n\n"

    # Start architecture section
    wrapper_vhdl += f"architecture Behavioral of {wrapper_entity_name} is\n"
    wrapper_vhdl += internal_signals_declaration
    wrapper_vhdl += "begin\n"
    wrapper_vhdl += flatten_unflatten_logic_code

    # Entity instantiation with port mapping
    wrapper_vhdl += f"    {entity_name}_inst: entity work.{entity_name}\n"
    wrapper_vhdl += "        port map (\n"
    wrapper_vhdl += port_map_code.rstrip(',\n')  # Remove the trailing comma
    wrapper_vhdl += "\n        );\n"
    wrapper_vhdl += "end Behavioral;"

    show_vhdl_code(wrapper_vhdl)




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

vhdl_input_label = tk.Label(root, text="Paste the VHDL entity here:")
vhdl_input_label.pack()
vhdl_input = scrolledtext.ScrolledText(root, height=10, width=80)
vhdl_input.pack()

analyze_button = ttk.Button(root, text="Analyze VHDL", command=analyze_vhdl)
analyze_button.pack()

tree = ttk.Treeview(root, columns=("Name", "Direction", "Type", "Range", "Flatten"), show="headings")
tree.heading("Name", text="Signal Name")
tree.heading("Direction", text="Direction")
tree.heading("Type", text="Type")
tree.heading("Range", text="Range")
tree.heading("Flatten", text="Flatten Options")
tree.pack(expand=True, fill="both")

flatten_button = ttk.Button(root, text="Flatten Signal", command=on_flatten_signal)
flatten_button.pack()

generate_button = ttk.Button(root, text="Generate Wrapper", command=generate_wrapper)
generate_button.pack()

clear_button = ttk.Button(root, text="Clear", command=clear_all)
clear_button.pack(pady=5)

root.mainloop()
