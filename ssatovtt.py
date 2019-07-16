import argparse
# from pprint import pprint

parser = argparse.ArgumentParser(description="Convert SSA/ASS subtitles to WebVTT format")
parser.add_argument("ssa")
parser.add_argument("vtt")

def convert(in_file, out_file):
    with open(in_file, 'r') as f:
        ass = f.read().split("\n")

    # Process text into sections
    sections = {}
    section = []
    for i in ass:
        if not i:
            continue
        if i[0] == "[":
            if section:
                sections[key] = section
                section = []
            key = i[1:-1]
        else:
            section.append(i)
    if section:
        sections[key] = section
        section = []

    # print(sections)

    # Process info

    info = {}

    for i in sections['Script Info']:
        line = i.split(":")
        if len(line) > 1:
            info[line[0]] = line[1].strip()
        elif i.lstrip()[0] == ";":  # If it is a comment
            continue
        else:
            raise Exception("Unknown line in Script Info section: " + i)

    info['PlayResX'] = int(info['PlayResX'])
    info['PlayResY'] = int(info['PlayResY'])

    # print(info)

    # Process styles

    styles = {}
    FORMAT = "Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,TertiaryColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,AlphaLevel,Encoding".split(",")

    for line in sections['V4+ Styles']:
        if line[:7] == "Format:":
            # File defines it's own format, use it
            FORMAT = [i.strip() for i in line[7:].strip().split(",")]
        elif line[:6] == "Style:":
            style_list = line[6:].strip().split(",")
            style = {}
            for i, value in enumerate(style_list):
                style[FORMAT[i]] = value
            styles[style.pop('Name').replace(" ", "")] = style

    # pprint(styles)

    # Process captions

    captions = []
    FORMAT = "Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text".split(",")
    # Compensation for captions that include commas
    format_length = len(FORMAT) - 1
    for line in sections['Events']:
        if line[:7] == "Format:":   # Process Format lines
            # File defines it's own format, use it
            FORMAT = [i.strip() for i in line[7:].strip().split(",")]
            format_length = len(FORMAT) - 1
        elif line[:9] == "Dialogue:":   # Process Dialogue lines
            dialogue_list = line[6:].strip().split(",")
            dialogue = {}
            for i, value in enumerate(dialogue_list):
                # Some text has commas in it which gets broken up by the comma split, append it back in
                if i > format_length:
                    print(dialogue)
                    print(dialogue['Text'])
                    dialogue['Text'] += "," + value
                    continue
                dialogue[FORMAT[i]] = value
            captions.append(dialogue)
    # pprint(captions)

    # By this point, we have now collected the data into three structures, info, styles and captions


    # Rewrite timestamps
    def rewrite_timestamp(timestamp):
        # Split off the milliseconds
        first_split = timestamp.split(".")
        # Split the hhmmss part
        hhmmss = first_split[0].split(":")
        ms = first_split[1]

        # Make sure ms is three digits
        while len(ms) < 3:
            ms += "0"

        # Remove hours if zero
        if len(hhmmss) == 3 and (hhmmss[0] == "0" or hhmmss[0] == "00"):
            hhmmss.pop(0)

        # Reassemble
        return ":".join(hhmmss) + "." + ms

    # Reprocess styles
    for style in styles:
        styles[style]['MarginR'] = int(styles[style]['MarginR'])
        styles[style]['MarginL'] = int(styles[style]['MarginL'])
        styles[style]['MarginV'] = int(styles[style]['MarginV'])

    # Reprocess captions

    # Some lines may get split due to local styling differences
    insert_list = []

    for line_number, line in enumerate(captions):
        line['Start'] = rewrite_timestamp(line['Start'])
        line['End'] = rewrite_timestamp(line['End'])
        # Process character turns
        line['Text'] = line['Text'].replace('\\N', '\n')

        full_text = ""
        parts = line['Text'].split("{")

        # Create a separate variable tracking our current line as we may be creating more lines
        current_line = line
        # Flag to append extra line at end of process if we made one
        extra_lines = 0
        for i, part in enumerate(parts):
            if not part:
                continue
            # Replace spaces in styles
            current_line['Style'] = current_line['Style'].replace(' ', '')

            local_style = {'Italic': styles[current_line['Style']]['Italic'] == "-1", 'Bold': styles[current_line['Style']]['Bold'] == "-1", "Position": None, "Newline": False}
            part_text = part
            if i:
                # I'm running out of variable name ideas
                more_parts = part.split("}")
                local_flags = more_parts[0].split("\\")
                part_text = more_parts[1]
                # process local flags
                for flag in local_flags:
                    if flag == "i" or flag == "i1": # Turn italics on
                        local_style['Italic'] = True
                    elif flag == "i0":
                        local_style['Italic'] = False # Turn italics off
                    elif flag[:3] == "pos":         # Position
                        local_style['Position'] = [float(coord) for coord in flag[4:-1].split(",")]
                        local_style['Newline'] = True

            # Add styling
            if local_style['Bold']:
                part_text = "<b>{}</b>".format(part_text)
            if local_style['Italic']:
                part_text = "<i>{}</i>".format(part_text)
            if local_style['Newline']:
                # If we have already created extra lines,
                if extra_lines:
                    # commit the previous stuff before this one
                    current_line["Text"] = full_text
                    insert_list.append([line_number, current_line])
                    # and move us to a new line
                    full_text = ''
                    current_line = current_line.copy()
                extra_lines += 1
            if local_style['Position']:
                # Program in margins that will get evaluated correctly later
                current_line['MarginL'] = round(local_style['Position'][0] - (info['PlayResX'] / 2) + 1)
                # The 1 is because 0 defaults to the style's margins
                current_line['MarginR'] = 1
                current_line['MarginV'] = round(local_style['Position'][1])

            full_text += part_text
        if extra_lines > 1:
            # Insert final line
            current_line["Text"] = full_text
            insert_list.append([line_number, current_line])
            # Insert newly created lines
            reversed(insert_list)
            # insert backwards because indicices will change
            for line in insert_list:
                captions.insert(line[0], line[1])
        else:
            line["Text"] = full_text


    # Final rewrite

    vtt = "WEBVTT\n\n"

    # Write out the CSS styles
    # Apparently no modern browser supports this. I wasted 1.5 hrs debugging this for nothing :((((
    # vtt += "STYLE\n"
    for style in styles:
        font = []
        if styles[style]['Bold'] == "-1":
            font.append("bold")
        if styles[style]['Italic'] == "-1":
            font.append("italic")
        if font:
            vtt += "STYLE\n." + style + " {font: " + " ".join(font) + ";}\n"

    vtt += "\n"

    # Final rewrite for captions

    for caption in captions:
        v_flag = False
        p_flag = ""
        name = ""
        style = ""
        text = ''
        # Create position data
        position = {'left': int(caption['MarginL']), 'right': int(caption['MarginR']), 'bottom': int(caption['MarginV'])}
        if not position['left']:
            position['left'] = styles[caption['Style']]['MarginL']
        if not position['right']:
            position['right'] = styles[caption['Style']]['MarginR']
        if not position['bottom']:
            position['bottom'] = styles[caption['Style']]['MarginV']
        # If we have position data, write it out
        if position['left'] or position['right'] or position['bottom']:
            if position['bottom']:
                # Percentage is not supported meaning we have to use line numbers. I have no idea
                # how many lines are in a video but 16 seems to work kinda
                p_flag += " line:-{}".format(round(position['bottom'] / info['PlayResY'] * 16, 4))
            # There isn't a straight analog for horizontal positioning so I'm taking the difference between the left and
            # right margins and using that.
            if position['left'] != position['right']:
                p_flag += " position:{}%".format(round((position['left'] - position['right']) / info['PlayResX'] * 100 + 50))

        if caption["Name"]:
            v_flag = True
            name = " " + caption["Name"]
        if caption["Style"]:
            v_flag = True
            style = "." + caption["Style"]

        text = caption["Text"]

        if v_flag:
            text = "<v{style}{name}>{text}</v>".format(style=style, name=name, text=text)

        vtt_caption = "{Start} --> {End}{position}\n{Text}\n\n".format(Start=caption['Start'], End=caption['End'], Text=text, position=p_flag)
        vtt += vtt_caption

    with open(out_file, 'w') as f:
        f.write(vtt)

args = parser.parse_args()
# print(args)
if args:
    convert(args.ssa, args.vtt)

