def compact_list(lst, type=None):
    if type == "notify":
        compacted_list = []
        i = 0
        while i < len(lst):
            item = lst[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if (
                    last_item[2]["end"] == item[2]["start"]
                    and last_item[2]["code"] == item[2]["code"]
                ):
                    last_item[1]["end"] = item[1]["end"]
                    last_item[2]["end"] = item[2]["end"]
                    i += 1
                    continue
            compacted_list.append(item)
            i += 1

    else:
        compacted_list = []
        i = 0
        while i < len(lst):
            item = lst[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if last_item.end == item.start and last_item.summary == item.summary:
                    last_item.end = item.end

                    i += 1
                    continue
            compacted_list.append(item)
            i += 1
    return compacted_list
