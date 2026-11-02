Scriptname LucyCompanionSensorScript extends Quest

Actor Property LucyRef Auto
ObjectReference Property Vault111ExitMarkerRef Auto
GlobalVariable Property GlobWaitMode Auto
GlobalVariable Property GlobRecruited Auto
GlobalVariable Property GlobAffinity Auto
Potion Property CmdAskItem Auto
Potion Property CmdFollowWaitItem Auto
Potion Property CmdLoreItem Auto
Potion Property CmdSummonItem Auto
Armor Property Vault33SuitItem Auto
Book Property LucyJournalItem Auto
Message Property MesgRecruitMenu Auto
Message Property MesgCompanionMenu Auto
Message Property MesgStoryIntro Auto
Message Property MesgAffinityStatus Auto
Message Property MesgPerkUnlocked Auto
Perk Property CompLucyPerk Auto

bool bInitialized = false
bool bFaceRefreshedV2 = false
bool bCompanionSystemV3 = false
bool bCompanionSystemV4 = false
bool bHasGreetedAtV111 = false
bool bTier500Reached = false
bool bTier750Reached = false
bool bPerkGranted = false
bool bWasInCombat = false
bool bWasBleedingOut = false
int iHeartbeatCounter = 0

int iLastQuests = -1
int iLastLocks = -1
int iLastHacks = -1
int iLastBuilt = -1
int iLastCrafted = -1
int iLastMurders = -1
int iLastPockets = -1
int iLastTrespasses = -1
int iLastAddictions = -1

int iTimerStartup = 1
int iTimerLoop = 2

Event OnQuestInit()
    Debug.OpenUserLog("LucyCompanionBridge")
    StartTimer(2.5, iTimerStartup)
EndEvent

bool Function IsLucyRecruited()
    if GlobRecruited != None && GlobRecruited.GetValue() >= 0.5
        return true
    endif
    return false
EndFunction

Function EnsurePlayerItems()
    Actor kPlayer = Game.GetPlayer()
    if kPlayer == None
        return
    endif
    if CmdAskItem != None && kPlayer.GetItemCount(CmdAskItem) < 1
        kPlayer.AddItem(CmdAskItem, 1, true)
    endif
    if CmdFollowWaitItem != None && kPlayer.GetItemCount(CmdFollowWaitItem) < 1
        kPlayer.AddItem(CmdFollowWaitItem, 1, true)
    endif
    if CmdLoreItem != None && kPlayer.GetItemCount(CmdLoreItem) < 1
        kPlayer.AddItem(CmdLoreItem, 1, true)
    endif
    if CmdSummonItem != None && kPlayer.GetItemCount(CmdSummonItem) < 1
        kPlayer.AddItem(CmdSummonItem, 1, true)
    endif
EndFunction

Function SyncTrackedStatsBaseline()
    iLastQuests = Game.QueryStat("Quests Completed")
    iLastLocks = Game.QueryStat("Locks Picked")
    iLastHacks = Game.QueryStat("Computers Hacked")
    iLastBuilt = Game.QueryStat("Objects Built")
    iLastCrafted = Game.QueryStat("Weapons Improved") + Game.QueryStat("Armor Improved")
    iLastMurders = Game.QueryStat("Murders")
    iLastPockets = Game.QueryStat("Pockets Picked")
    iLastTrespasses = Game.QueryStat("Trespasses")
    iLastAddictions = Game.QueryStat("Times Addicted")
EndFunction

Function MoveLucyToVault111Esplanade()
    if LucyRef == None
        return
    endif
    if LucyRef.IsDisabled()
        LucyRef.Enable(false)
    endif
    if LucyRef.IsDead()
        LucyRef.Resurrect()
    endif
    LucyRef.SetEssential(true)
    LucyRef.SetProtected(true)
    LucyRef.SetPlayerTeammate(false, false, false)
    if GlobWaitMode != None
        GlobWaitMode.SetValue(1.0)
    endif
    if LucyJournalItem != None && LucyRef.GetItemCount(LucyJournalItem) < 1
        LucyRef.AddItem(LucyJournalItem, 1, true)
    endif
    if Vault111ExitMarkerRef != None
        ; Positioned by the Vault 111 surface control stand (~12.5m off the circular elevator platform)
        LucyRef.MoveTo(Vault111ExitMarkerRef, 490.0, 730.0, 10.0, false)
        LucyRef.SetAngle(0.0, 0.0, 216.0)
        LucyRef.MoveToNearestNavmeshLocation()
    endif
    LucyRef.EvaluatePackage()
EndFunction

Function InitializeCompanionV3()
    bCompanionSystemV3 = true
    bCompanionSystemV4 = true
    bHasGreetedAtV111 = false
    SyncTrackedStatsBaseline()
    if GlobAffinity != None && GlobAffinity.GetValue() <= 0.0
        GlobAffinity.SetValue(250.0)
    endif
    if GlobRecruited != None
        GlobRecruited.SetValue(0.0)
    endif
    if GlobWaitMode != None
        GlobWaitMode.SetValue(1.0)
    endif
    EnsurePlayerItems()
    MoveLucyToVault111Esplanade()
    Debug.Notification("[Vault 33 Signal: Lucy MacLean is waiting at the Vault 111 exterior overlook]")
EndFunction

Function SetupLucyActor(bool abForceMove)
    if LucyRef == None
        return
    endif
    Actor kPlayer = Game.GetPlayer()
    if kPlayer == None
        return
    endif
    if !bFaceRefreshedV2
        bFaceRefreshedV2 = true
        LucyRef.Disable(false)
        Utility.Wait(0.1)
        LucyRef.Enable(false)
    elseif LucyRef.IsDisabled()
        LucyRef.Enable(false)
    endif
    if LucyRef.IsDead()
        LucyRef.Resurrect()
    endif
    LucyRef.SetEssential(true)
    LucyRef.SetProtected(true)

    if !IsLucyRecruited()
        LucyRef.SetPlayerTeammate(false, false, false)
        if GlobWaitMode != None && GlobWaitMode.GetValue() < 0.5
            GlobWaitMode.SetValue(1.0)
        endif
        LucyRef.EvaluatePackage()
        return
    endif

    LucyRef.SetPlayerTeammate(true, true, true)
    LucyRef.AllowBleedoutDialogue(true)

    bool bWait = false
    if GlobWaitMode != None && GlobWaitMode.GetValue() >= 0.5
        bWait = true
    endif

    if abForceMove || (!bWait && (LucyRef.GetParentCell() != kPlayer.GetParentCell() || kPlayer.GetDistance(LucyRef) > 3600.0))
        float fAng = kPlayer.GetAngleZ()
        float fOffX = 160.0 * Math.Sin(fAng)
        float fOffY = 160.0 * Math.Cos(fAng)
        LucyRef.MoveTo(kPlayer, fOffX, fOffY, 0.0, false)
        LucyRef.MoveToNearestNavmeshLocation()
    endif
    LucyRef.EvaluatePackage()
EndFunction

Function ChangeAffinity(float afDelta, string asReasonHud, string asEventType)
    if GlobAffinity == None || !IsLucyRecruited()
        return
    endif
    float fCur = GlobAffinity.GetValue()
    float fNew = fCur + afDelta
    if fNew < 0.0
        fNew = 0.0
    elseif fNew > 1000.0
        fNew = 1000.0
    endif
    GlobAffinity.SetValue(fNew)
    int iNew = fNew as int
    Debug.Notification(asReasonHud + " [Affinity: " + iNew + "/1000]")

    Actor kPlayer = Game.GetPlayer()
    if fNew >= 1000.0 && !bPerkGranted
        bPerkGranted = true
        bTier750Reached = true
        bTier500Reached = true
        if kPlayer != None && CompLucyPerk != None && !kPlayer.HasPerk(CompLucyPerk)
            kPlayer.AddPerk(CompLucyPerk, false)
        endif
        TriggerSnapshot("affinity_max_perk")
        if MesgPerkUnlocked != None
            MesgPerkUnlocked.Show()
        endif
        return
    elseif fNew >= 750.0 && !bTier750Reached
        bTier750Reached = true
        Debug.Notification("[Lucy MacLean now considers you her Confidant in the Commonwealth (750/1000)]")
    elseif fNew >= 500.0 && !bTier500Reached
        bTier500Reached = true
        Debug.Notification("[Lucy MacLean now considers you a True Vault 33 Friend (500/1000)]")
    endif

    TriggerSnapshot(asEventType)
EndFunction

Function CheckTrackedStatsForAffinity()
    if !IsLucyRecruited()
        return
    endif
    if iLastQuests < 0
        SyncTrackedStatsBaseline()
        return
    endif

    int iCurMurders = Game.QueryStat("Murders")
    if iCurMurders > iLastMurders
        iLastMurders = iCurMurders
        ChangeAffinity(-80.0, "Lucy hated that cold-blooded murder! (-80)", "affinity_hate")
        return
    endif

    int iCurPockets = Game.QueryStat("Pockets Picked")
    if iCurPockets > iLastPockets
        iLastPockets = iCurPockets
        ChangeAffinity(-25.0, "Lucy disliked you stealing from others (-25)", "affinity_dislike")
        return
    endif

    int iCurTrespasses = Game.QueryStat("Trespasses")
    if iCurTrespasses > iLastTrespasses
        iLastTrespasses = iCurTrespasses
        ChangeAffinity(-20.0, "Lucy disliked that trespassing (-20)", "affinity_dislike")
        return
    endif

    int iCurAddictions = Game.QueryStat("Times Addicted")
    if iCurAddictions > iLastAddictions
        iLastAddictions = iCurAddictions
        ChangeAffinity(-30.0, "Lucy is worried about your chem addiction (-30)", "affinity_dislike")
        return
    endif

    int iCurQuests = Game.QueryStat("Quests Completed")
    if iCurQuests > iLastQuests
        iLastQuests = iCurQuests
        ChangeAffinity(45.0, "Lucy loved that you helped people in the Commonwealth! (+45)", "affinity_love")
        return
    endif

    int iCurHacks = Game.QueryStat("Computers Hacked")
    if iCurHacks > iLastHacks
        iLastHacks = iCurHacks
        ChangeAffinity(20.0, "Lucy liked your terminal hacking skills (+20)", "affinity_like")
        return
    endif

    int iCurLocks = Game.QueryStat("Locks Picked")
    if iCurLocks > iLastLocks
        iLastLocks = iCurLocks
        ChangeAffinity(15.0, "Lucy liked your resourcefulness with that lock (+15)", "affinity_like")
        return
    endif

    int iCurCrafted = Game.QueryStat("Weapons Improved") + Game.QueryStat("Armor Improved")
    if iCurCrafted > iLastCrafted
        iLastCrafted = iCurCrafted
        ChangeAffinity(15.0, "Lucy liked that you maintained your gear (+15)", "affinity_like")
        return
    endif

    int iCurBuilt = Game.QueryStat("Objects Built")
    if iCurBuilt >= iLastBuilt + 3
        iLastBuilt = iCurBuilt
        ChangeAffinity(15.0, "Lucy liked that you are rebuilding the settlement (+15)", "affinity_like")
        return
    endif
EndFunction

Function RecruitLucy()
    Actor kPlayer = Game.GetPlayer()
    if GlobRecruited != None
        GlobRecruited.SetValue(1.0)
    endif
    if GlobWaitMode != None
        GlobWaitMode.SetValue(0.0)
    endif
    if GlobAffinity != None && GlobAffinity.GetValue() <= 0.0
        GlobAffinity.SetValue(250.0)
    endif
    SyncTrackedStatsBaseline()
    EnsurePlayerItems()
    if kPlayer != None
        if LucyJournalItem != None && kPlayer.GetItemCount(LucyJournalItem) < 1
            kPlayer.AddItem(LucyJournalItem, 1, false)
        endif
        if Vault33SuitItem != None && kPlayer.GetItemCount(Vault33SuitItem) < 1
            kPlayer.AddItem(Vault33SuitItem, 1, false)
        endif
    endif
    SetupLucyActor(false)
    int iAff = 250
    if GlobAffinity != None
        iAff = GlobAffinity.GetValue() as int
    endif
    Debug.Notification("[Lucy MacLean is now your companion! (Affinity: " + iAff + "/1000) | Press E on her or F8 to chat]")
    TriggerSnapshot("recruited")
EndFunction

Function CommandDismissLucy()
    if GlobRecruited != None
        GlobRecruited.SetValue(0.0)
    endif
    if GlobWaitMode != None
        GlobWaitMode.SetValue(1.0)
    endif
    MoveLucyToVault111Esplanade()
    Debug.Notification("[Lucy MacLean has returned to her camp at the Vault 111 exterior overlook]")
    TriggerSnapshot("dismissed")
EndFunction

Function OnLucyActivated()
    if LucyRef == None
        return
    endif
    if !IsLucyRecruited()
        if MesgRecruitMenu == None
            RecruitLucy()
            return
        endif
        int iChoice = MesgRecruitMenu.Show()
        if iChoice == 0
            RecruitLucy()
        elseif iChoice == 1
            if MesgStoryIntro != None
                int iStoryChoice = MesgStoryIntro.Show()
                if iStoryChoice == 0
                    RecruitLucy()
                else
                    Debug.Notification("[Lucy MacLean will wait for you at the Vault 111 exterior overlook]")
                    TriggerSnapshot("recruit_declined")
                endif
            else
                RecruitLucy()
            endif
        else
            Debug.Notification("[Lucy MacLean will wait for you at the Vault 111 exterior overlook]")
            TriggerSnapshot("recruit_declined")
        endif
        return
    endif

    ; If already recruited, open the Full Companion Menu
    if MesgCompanionMenu == None
        CommandAskWhatDoYouThink()
        return
    endif
    float fAff = 250.0
    if GlobAffinity != None
        fAff = GlobAffinity.GetValue()
    endif
    int iBtn = MesgCompanionMenu.Show(fAff)
    if iBtn == 0
        CommandAskWhatDoYouThink()
    elseif iBtn == 1
        CommandTellLoreStory()
    elseif iBtn == 2
        LucyRef.OpenInventory(true)
    elseif iBtn == 3
        CommandToggleFollowWait()
    elseif iBtn == 4
        if MesgAffinityStatus != None
            MesgAffinityStatus.Show(fAff)
        endif
    elseif iBtn == 5
        CommandDismissLucy()
    endif
EndFunction

Event OnTimer(int aiTimerID)
    Debug.OpenUserLog("LucyCompanionBridge")

    if !bCompanionSystemV3
        InitializeCompanionV3()
        bInitialized = true
        StartTimer(5.0, iTimerLoop)
        return
    elseif !bCompanionSystemV4
        bCompanionSystemV4 = true
        if !IsLucyRecruited()
            bHasGreetedAtV111 = false
            MoveLucyToVault111Esplanade()
        endif
    endif

    EnsurePlayerItems()

    if aiTimerID == iTimerStartup
        SetupLucyActor(false)
        bInitialized = true
        StartTimer(5.0, iTimerLoop)
    elseif aiTimerID == iTimerLoop
        Actor kPlayer = Game.GetPlayer()
        if kPlayer != None && LucyRef != None
            if !IsLucyRecruited()
                bool bOffElevator = true
                if Vault111ExitMarkerRef != None && kPlayer.GetDistance(Vault111ExitMarkerRef) <= 320.0
                    bOffElevator = false
                endif
                if !bHasGreetedAtV111 && bOffElevator && kPlayer.GetDistance(LucyRef) < 520.0
                    bHasGreetedAtV111 = true
                    Debug.Notification("[Lucy MacLean (Vault 33) waves at you — Walk up and press E to talk to her]")
                    EmitSnapshot("v111_greeting")
                endif
                StartTimer(5.0, iTimerLoop)
                return
            endif

            SetupLucyActor(false)
            CheckTrackedStatsForAffinity()

            bool bNowCombat = kPlayer.IsInCombat() || LucyRef.IsInCombat()
            bool bNowBleed = LucyRef.IsBleedingOut() || (LucyRef.GetValuePercentage(Game.GetHealthAV()) < 0.25)

            if bNowCombat && !bWasInCombat
                bWasInCombat = true
                iHeartbeatCounter = 0
                EmitSnapshot("combat_start")
            elseif !bNowCombat && bWasInCombat
                bWasInCombat = false
                iHeartbeatCounter = 0
                EmitSnapshot("combat_end")
            elseif bNowBleed && !bWasBleedingOut
                bWasBleedingOut = true
                iHeartbeatCounter = 0
                EmitSnapshot("companion_hurt")
            elseif !bNowBleed && bWasBleedingOut
                bWasBleedingOut = false
                iHeartbeatCounter = 0
                EmitSnapshot("companion_recovered")
            else
                iHeartbeatCounter += 1
                if iHeartbeatCounter >= 5
                    iHeartbeatCounter = 0
                    EmitSnapshot("heartbeat")
                endif
            endif
        endif
        StartTimer(5.0, iTimerLoop)
    endif
EndEvent

Function TriggerSnapshot(string asEventName)
    Debug.OpenUserLog("LucyCompanionBridge")
    iHeartbeatCounter = 0
    EmitSnapshot(asEventName)
EndFunction

Function CommandAskWhatDoYouThink()
    if !IsLucyRecruited()
        Debug.Notification("[Lucy MacLean is waiting at the Vault 111 exterior overlook to be recruited]")
        return
    endif
    Debug.Notification("[Asking Lucy MacLean...]")
    TriggerSnapshot("what_do_you_think")
EndFunction

Function CommandToggleFollowWait()
    if !IsLucyRecruited()
        Debug.Notification("[Recruit Lucy MacLean at the Vault 111 overlook first]")
        return
    endif
    if GlobWaitMode == None
        return
    endif
    if GlobWaitMode.GetValue() < 0.5
        GlobWaitMode.SetValue(1.0)
        if LucyRef != None
            LucyRef.EvaluatePackage()
        endif
        Debug.Notification("[Lucy MacLean: Waiting here]")
        TriggerSnapshot("wait_here")
    else
        GlobWaitMode.SetValue(0.0)
        SetupLucyActor(false)
        Debug.Notification("[Lucy MacLean: Following you — Let's get to it!]")
        TriggerSnapshot("follow_me")
    endif
EndFunction

Function CommandTellLoreStory()
    if !IsLucyRecruited()
        Debug.Notification("[Lucy MacLean is waiting at the Vault 111 exterior overlook]")
        return
    endif
    Debug.Notification("[Lucy MacLean: Vault 33 & Wasteland Chat...]")
    TriggerSnapshot("campfire")
EndFunction

Function CommandSummonLucy()
    if !IsLucyRecruited()
        Actor kPlayer = Game.GetPlayer()
        if kPlayer != None && LucyRef != None
            float fAng = kPlayer.GetAngleZ()
            LucyRef.MoveTo(kPlayer, 150.0 * Math.Sin(fAng), 150.0 * Math.Cos(fAng), 0.0, false)
            LucyRef.MoveToNearestNavmeshLocation()
            OnLucyActivated()
        endif
        return
    endif
    if GlobWaitMode != None
        GlobWaitMode.SetValue(0.0)
    endif
    if LucyRef != None
        LucyRef.ResetHealthAndLimbs()
    endif
    bFaceRefreshedV2 = false
    SetupLucyActor(true)
    Debug.Notification("[Lucy MacLean moved to your position — Let's get to it!]")
    TriggerSnapshot("follow_me")
EndFunction

string Function BoolToJson(bool abVal)
    if abVal
        return "true"
    endif
    return "false"
EndFunction

string Function BuildActorJson(Actor akPlayer, Actor akOther)
    if akOther == None || akOther == akPlayer || akOther == LucyRef
        return ""
    endif
    int iBaseFID = 0
    ActorBase kBase = akOther.GetActorBase()
    if kBase != None
        iBaseFID = kBase.GetFormID()
    endif
    int iRaceFID = 0
    Race kRace = akOther.GetRace()
    if kRace != None
        iRaceFID = kRace.GetFormID()
    endif
    int iDistM = (akPlayer.GetDistance(akOther) * 0.01428) as int
    bool bDead = akOther.IsDead()
    bool bCombat = akOther.IsInCombat()
    bool bHostile = akOther.IsHostileToActor(akPlayer)

    return "{\"base_fid\":" + iBaseFID + ",\"race_fid\":" + iRaceFID + ",\"dist_m\":" + iDistM + ",\"dead\":" + BoolToJson(bDead) + ",\"in_combat\":" + BoolToJson(bCombat) + ",\"hostile\":" + BoolToJson(bHostile) + "}"
EndFunction

Function EmitSnapshot(string asEventName)
    Actor kPlayer = Game.GetPlayer()
    if kPlayer == None
        return
    endif

    float fGameTime = Utility.GetCurrentGameTime()
    int iDays = fGameTime as int
    float fHoursTotal = (fGameTime - iDays) * 24.0
    int iHour = fHoursTotal as int
    int iMin = ((fHoursTotal - iHour) * 60.0) as int
    string sHour = "" + iHour
    if iHour < 10
        sHour = "0" + iHour
    endif
    string sMin = "" + iMin
    if iMin < 10
        sMin = "0" + iMin
    endif
    string sGameHour = sHour + ":" + sMin

    int iLocFID = 0
    Location kLoc = kPlayer.GetCurrentLocation()
    if kLoc != None
        iLocFID = kLoc.GetFormID()
    endif

    int iCellFID = 0
    bool bInterior = false
    Cell kCell = kPlayer.GetParentCell()
    if kCell != None
        iCellFID = kCell.GetFormID()
        bInterior = kCell.IsInterior()
    endif

    int iWSFID = 0
    WorldSpace kWS = kPlayer.GetWorldSpace()
    if kWS != None
        iWSFID = kWS.GetFormID()
    endif

    int iWthrFID = 0
    int iWthrClass = 0
    Weather kWthr = Weather.GetCurrentWeather()
    if kWthr != None
        iWthrFID = kWthr.GetFormID()
        iWthrClass = kWthr.GetClassification()
    endif

    int iPlayerHP = (kPlayer.GetValuePercentage(Game.GetHealthAV()) * 100.0) as int
    bool bPlayerCombat = kPlayer.IsInCombat()
    bool bPlayerSneak = kPlayer.IsSneaking()
    bool bPlayerPA = kPlayer.IsInPowerArmor()
    int iWeapFID = 0
    Weapon kWeap = kPlayer.GetEquippedWeapon()
    if kWeap != None
        iWeapFID = kWeap.GetFormID()
    endif

    int iLucyHP = 100
    bool bLucyCombat = false
    bool bLucyBleed = false
    int iLucyDistM = 2
    bool bRecruited = IsLucyRecruited()
    int iAffinity = 250
    if GlobAffinity != None
        iAffinity = GlobAffinity.GetValue() as int
    endif
    string sStance = "following"
    if !bRecruited
        sStance = "unrecruited_v111"
    elseif GlobWaitMode != None && GlobWaitMode.GetValue() >= 0.5
        sStance = "waiting"
    endif
    if LucyRef != None
        iLucyHP = (LucyRef.GetValuePercentage(Game.GetHealthAV()) * 100.0) as int
        bLucyCombat = LucyRef.IsInCombat()
        bLucyBleed = LucyRef.IsBleedingOut()
        iLucyDistM = (kPlayer.GetDistance(LucyRef) * 0.01428) as int
    endif

    Actor kAct1 = kPlayer.GetCombatTarget()
    if kAct1 == None && LucyRef != None
        kAct1 = LucyRef.GetCombatTarget()
    endif
    Actor kAct2 = Game.FindClosestActorFromRef(kPlayer, 1500.0)
    if kAct2 == kPlayer || kAct2 == LucyRef || kAct2 == kAct1
        kAct2 = None
    endif
    Actor kAct3 = Game.FindRandomActorFromRef(kPlayer, 2000.0)
    if kAct3 == kPlayer || kAct3 == LucyRef || kAct3 == kAct1 || kAct3 == kAct2
        kAct3 = None
    endif

    string sNearby = ""
    string sA1 = BuildActorJson(kPlayer, kAct1)
    if sA1 != ""
        sNearby = sA1
    endif
    string sA2 = BuildActorJson(kPlayer, kAct2)
    if sA2 != ""
        if sNearby != ""
            sNearby = sNearby + "," + sA2
        else
            sNearby = sA2
        endif
    endif
    string sA3 = BuildActorJson(kPlayer, kAct3)
    if sA3 != ""
        if sNearby != ""
            sNearby = sNearby + "," + sA3
        else
            sNearby = sA3
        endif
    endif

    string sPlayerJson = "{\"hp\":" + iPlayerHP + ",\"in_combat\":" + BoolToJson(bPlayerCombat) + ",\"sneaking\":" + BoolToJson(bPlayerSneak) + ",\"in_power_armor\":" + BoolToJson(bPlayerPA) + ",\"weapon_fid\":" + iWeapFID + "}"
    string sCompJson = "{\"hp\":" + iLucyHP + ",\"in_combat\":" + BoolToJson(bLucyCombat) + ",\"bleedout\":" + BoolToJson(bLucyBleed) + ",\"distance_m\":" + iLucyDistM + ",\"recruited\":" + BoolToJson(bRecruited) + ",\"affinity\":" + iAffinity + ",\"stance\":\"" + sStance + "\"}"

    string sJson = "{\"event\":\"" + asEventName + "\",\"game_hour\":\"" + sGameHour + "\",\"loc_fid\":" + iLocFID + ",\"cell_fid\":" + iCellFID + ",\"ws_fid\":" + iWSFID + ",\"interior\":" + BoolToJson(bInterior) + ",\"weather_fid\":" + iWthrFID + ",\"weather_class\":" + iWthrClass + ",\"player\":" + sPlayerJson + ",\"companion\":" + sCompJson + ",\"nearby_raw\":[" + sNearby + "]}"

    Debug.TraceUser("LucyCompanionBridge", "[LUCY_SNAPSHOT] " + sJson)
EndFunction
