
            local last_species = 0
            local pulse_timer = 0
            console:log(">> WORKER 3 LUA LOADED SUCCESSFULLY <<")
            
            function checkEncounter()
                -- Pulse every ~5 seconds (60 frames * 5) to show script is alive
                pulse_timer = pulse_timer + 1
                if pulse_timer > 300 then
                    console:log("Worker 3 Pulse: Script is running...")
                    pulse_timer = 0
                end

                local species = emu:read16(0x0202402C)
                if species > 0 and species < 412 then
                    if species ~= last_species then
                        console:log("ENCOUNTER DETECTED: ID " .. species)
                        local f = io.open("/home/michael/Projects/gamedev/pokemon/poketally/data/bridge/found_3.txt", "w")
                        if f then 
                            f:write(tostring(species))
                            f:close() 
                        end
                        last_species = species
                    end
                else
                    last_species = 0
                end
            end
            emu:registerAfter(checkEncounter)
            