
            local last_species = 0
            local timer = 0
            console:log(">> DEEP SCAN ACTIVE - WATCHING 0x02024020+ <<")
            
            function checkEncounter()
                timer = timer + 1
                local base = 0x02024020 -- Start slightly earlier to see the whole block
                
                -- Print diagnostics every 120 frames (~2 seconds)
                if timer > 120 then
                    local line = ""
                    for offset = 0, 16, 2 do
                        local val = emu:read16(base + offset)
                        line = line .. string.format("[%X]:%d  ", base + offset, val)
                    end
                    console:log(line)
                    timer = 0
                end

                -- Logic to actually catch the Pokemon (we'll refine the address based on your results)
                -- Checking the most likely candidates for FireRed/LeafGreen
                local candidate1 = emu:read16(0x0202402C)
                local candidate2 = emu:read16(0x0202402E)
                local candidate3 = emu:read16(0x0202443C) -- Common alt for some ROM hacks/versions
                
                local found = 0
                if candidate1 > 0 and candidate1 < 412 then found = candidate1
                elseif candidate2 > 0 and candidate2 < 412 then found = candidate2
                elseif candidate3 > 0 and candidate3 < 412 then found = candidate3 end

                if found > 0 and found ~= last_species then
                    console:log("!! LOGGING ENCOUNTER: ID " .. found)
                    local f = io.open("/home/michael/Projects/gamedev/pokemon/poketally/data/bridge/found_1.txt", "w")
                    if f then f:write(tostring(found)); f:close() end
                    last_species = found
                elseif found == 0 then
                    last_species = 0
                end
            end
            
            callbacks:add("frame", checkEncounter)
            