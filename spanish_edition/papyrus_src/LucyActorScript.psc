Scriptname LucyActorScript extends Actor

Quest Property LucyQuest Auto

Event OnLoad()
    Self.IgnoreFriendlyHits(true)
EndEvent

Event OnActivate(ObjectReference akActionRef)
    if akActionRef == Game.GetPlayer() && !Self.IsInCombat()
        LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
        if kSensor != None
            kSensor.OnLucyActivated()
        endif
    endif
EndEvent

Event OnCombatStateChanged(Actor akTarget, int aeCombatState)
    Actor kPlayer = Game.GetPlayer()
    Self.IgnoreFriendlyHits(true)
    if akTarget == kPlayer || Self.GetCombatTarget() == kPlayer || Self.IsHostileToActor(kPlayer)
        Self.StopCombat()
        Self.StopCombatAlarm()
        return
    endif
    LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
    if kSensor != None
        if aeCombatState == 1
            kSensor.TriggerSnapshot("combat_start")
        elseif aeCombatState == 0
            kSensor.TriggerSnapshot("combat_end")
        endif
    endif
EndEvent

Event OnEnterBleedout()
    Self.IgnoreFriendlyHits(true)
    LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
    if kSensor != None
        kSensor.TriggerSnapshot("companion_hurt")
    endif
EndEvent
