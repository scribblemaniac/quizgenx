#!/usr/bin/env python3

import argparse
import ast # ast.literal_eval()
import sys # sys.stdin / sys.stdout
from xml.etree import ElementTree
import copy # copy.deepcopy()
import os.path # os.path.join

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", help="A quiz file to read. If not specified stdin is used.")
parser.add_argument("-o", "--output", help="A file to write to. If not specified stdout is used.")
parser.add_argument("-v", "--verbose", help="Enable verbose output. Currently unimplemented.", action="store_true")
parser.add_argument("-t", "--theme", help="A theme directory. Defaults to themes/Classic", default="themes/Classic")
parser.add_argument("--format", help="The output format to use, currently only html is supported", default="html")
parser.add_argument("--disable-auto-br", help="Disables automatically adding line breaks to multi-line descriptions.", action="store_true")
args = parser.parse_args()

# TODO make useful errors
def parse_quiz(input_stream):
    def parse_group_heading(current_object, line):
        level = 0
        while line and line[0] == "=":
            line = line[1:]
            level += 1
        line = line.lstrip()
        
        # Special case for main title
        if level == 1:
            current_object["title"] = line
            
            return current_object
        
        while current_object["type"] != "group" or current_object["level"] >= level:
            current_object = current_object["parent"]
        
        group_object = { "type": "group", "parent": current_object, "level": level, "title": line, "description": "", "children": [], "advanced": {} }
        
        current_object["children"].append(group_object)
        
        return group_object
    
    def parse_group_ending(current_object, line):
        level = 0
        line = line[1:]
        while line and line[0] == "=":
            line = line[1:]
            level += 1
        
        while current_object["type"] != "group" or current_object["level"] >= level:
            current_object = current_object["parent"]
        
        return current_object
    
    def parse_question_heading(current_object, line):
        if current_object["type"] != "group":
            current_object = current_object["parent"]
        question_object = { "type": "question", "parent": current_object, "title": "", "description": "", "options": [], "advanced": {} }
        line = line[2:]
        if line:
            question_object["title"] = line.lstrip()
        current_object["children"].append(question_object)
        
        return question_object
    
    def parse_question_option(current_object, line):
        is_correct = False
        if line[1] == "=":
            line = line[2:].lstrip()
            is_correct = True
        else:
            line = line[1:].lstrip()
        
        current_object["options"].append((line, is_correct))
    
    def parse_advanced_settings(current_object, line):
        current_object["advanced"] = ast.literal_eval(line)
    
    def parse_description(current_object, line):
        if current_object["type"] == "question" and current_object["options"]:
            current_object["options"][-1] += "\n"
            current_object["options"][-1] += line
        else:
            if current_object["description"]:
                current_object["description"] += "\n"
            current_object["description"] += line

    def parse_line(current_object, line):
        if line.startswith("="):
            current_object = parse_group_heading(current_object, line)
        elif line.startswith("\="):
            current_object = parse_group_ending(current_object, line)
        elif line.startswith("--"):
            current_object = parse_question_heading(current_object, line)
        elif line.startswith("*"):
            parse_question_option(current_object, line)
        elif line.startswith("{") and line.endswith("}"):
            parse_advanced_settings(current_object, line)
        else:
            parse_description(current_object, line)
        
        return current_object
    
    quiz_object = { "type": "group", "parent": None, "level": 1, "title": "", "description": "", "children": [], "advanced": {} }
    
    current_object = quiz_object
    for line in input_stream:
        line = line.strip()
        if line and not line.startswith("#"):
            current_object = parse_line(current_object, line)
    
    return quiz_object

if args.input:
    file = open(args.input, "r")
    quiz = parse_quiz(file)
    file.close()
else:
    quiz = parse_quiz(sys.stdin)

def generate_html(quiz_object, template_path, output_stream):
    def add_text(text, element):
        text = "<temp>" + text + "</temp>"
        if not args.disable_auto_br:
            text = text.replace("\n", "<br />")
        temp = ElementTree.fromstring(text)
        for child in temp:
            element.append(child)
        element.text = temp.text
        element.tail = temp.tail
    
    def remove_name(element):
        if element.get("name") is not None:
            del element.attrib["name"]
        if element.get("x-name"):
            element.set("name", element.get("x-name"))
            del element.attrib["x-name"]
    
    def add_question(quiz_object, parent):
        wrapper = copy.deepcopy(question_template)
        remove_name(wrapper)
        parent.append(wrapper)
        title = wrapper.find(".//*[@name='title']")
        add_text(quiz_object["title"], title)
        remove_name(title)
        description = wrapper.find(".//*[@name='description']")
        add_text(quiz_object["description"], description)
        remove_name(description)
        options = wrapper.find(".//*[@name='options']")
        remove_name(options)
        option_template = options.find(".//*[@name='option']")
        remove_name(option_template)
        options.remove(option_template)
        correct_option_template = options.find(".//*[@name='correct-option']")
        remove_name(correct_option_template)
        options.remove(correct_option_template)
        for option in quiz_object["options"]:
            if option[1]:
                dom_option = copy.deepcopy(correct_option_template)
            else:
                dom_option = copy.deepcopy(option_template)
            add_text(option[0], dom_option)
            options.append(dom_option)
        if "attributes" in quiz_object["advanced"] and type(quiz_object["advanced"]["attributes"]) == list:
            for attr in quiz_object["advanced"]["attributes"]:
                if type(attr) == tuple and len(attr) == 2:
                    wrapper.set(attr[0], attr[1])
    
    def add_group(quiz_object, parent):
        group_level = quiz_object["level"]
        if group_level >= len(group_templates):
            group_level = 0
        wrapper = copy.deepcopy(group_templates[group_level])
        del wrapper.attrib["level"]
        if wrapper.get("x-level") is not None:
            wrapper.set("level", wrapper.get("x-level"))
            del wrapper.attrib["x-level"]
        remove_name(wrapper)
        parent.append(wrapper)
        title = wrapper.find(".//*[@name='title']")
        add_text(quiz_object["title"], title)
        remove_name(title)
        description = wrapper.find(".//*[@name='description']")
        add_text(quiz_object["description"], description)
        remove_name(description)
        children = wrapper.find(".//*[@name='children']")
        remove_name(children)
        for child in quiz_object["children"]:
            if child["type"] == "group":
                add_group(child, children)
            else:
                add_question(child, children)
        if "attributes" in quiz_object["advanced"] and type(quiz_object["advanced"]["attributes"]) == list:
            for attr in quiz_object["advanced"]["attributes"]:
                if type(attr) == tuple and len(attr) == 2:
                    wrapper.set(attr[0], attr[1])
    
    tree = ElementTree.parse(template_path)
    root = tree.getroot()
    body_content = root.find("body//*[@id='quizgenx-body-content']")
    if body_content is None:
        body_content = root.find("body[@id='quizgenx-body-content']")
    if body_content is None:
        body_content = root.find("body")
        if body_content is None:
            raise SyntaxError("Template at '" + template_path + "' does not contain a body")
        body_content = ElementTree.SubElement(body_content, "div", { "id": "quizgenx-body-content" })
    del body_content.attrib["id"]
    if body_content.get("x-id") is not None:
        body_content.set("id", body_content.get("x-id"))
        del body_content.attrib["x-id"]
    head = root.find("head")
    if head is None:
        raise SyntaxError("Template at '" + template_path + "' does not contain a head")
    
    templates = root.find(".//*[@id='quizgenx-templates']")
    if templates is None:
        raise SyntaxError("Template at '" + template_path + "' does not contain a templates group (id=quizgenx-templates)")
    root.find(".//*[@id='quizgenx-templates']..").remove(templates)
    
    # Get group templates
    group_templates = []
    if templates.find(".//*[@name='group'][@level='0']") is None:
        raise SyntaxError("Template at '" + template_path + "' does not contain a default group (name=group and level=0)")
    for group_template in templates.findall(".//*[@name='group'][@level]"):
        if not group_template.get("level").isdigit():
            continue
        level = int(group_template.get("level"))
        if level < 0:
            continue
        while len(group_templates) <= level:
            group_templates.append(None)
        group_templates[level] = group_template
    for i, template in enumerate(group_templates):
        if not template:
            group_templates[i] = group_templates[0]
    
    # Get question templates
    question_template = templates.find(".//*[@name='question']")
    if question_template is None:
        raise SyntaxError("Template at '" + template_path + "' does not contain a question template (name=question)")
    if question_template.find(".//*[@name='title']") is None:
        raise SyntaxError("Template at '" + template_path + "' has a question template, but it does not contain a title (name=title)")
    if question_template.find(".//*[@name='description']") is None:
        raise SyntaxError("Template at '" + template_path + "' has a question template, but it does not contain a description (name=description)")
    if question_template.find(".//*[@name='options']") is None:
        raise SyntaxError("Template at '" + template_path + "' has a question template, but it does not contain an options group (name=options)")
    if question_template.find(".//*[@name='options']//*[@name='option']") is None:
        raise SyntaxError("Template at '" + template_path + "' has a question template with options group, but the options group does not contain an option (name=option)")
    if question_template.find(".//*[@name='options']//*[@name='correct-option']") is None:
        raise SyntaxError("Template at '" + template_path + "' has a question template with options group, but the options group does not contain a correct option (name=correct-option)")
    
    current_quiz_object = quiz_object
    add_group(current_quiz_object, body_content)
    
    temp_title_element = ElementTree.fromstring("<temp>" + quiz_object["title"] + "</temp>")
    title_element = ElementTree.Element("title")
    title_element.text = "".join(temp_title_element.itertext())
    head.append(title_element)
    
    output_stream.write(ElementTree.tostring(root, method="html"))

if args.format == "html":
    if args.output:
        file = open(args.output, "wb")
        generate_html(quiz, os.path.join(args.theme, "template.html"), file)
        file.close()
    else:
        generate_html(quiz, os.path.join(args.theme, "template.html"), sys.stdin)
else:
    raise ValueError("Unsupported format '" + args.format + "'")
