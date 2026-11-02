Scriptname LucyActorScript extends Actor

Quest Property LucyQuest Auto

Event OnActivate(ObjectReference akActionRef)
    if akActionRef == Game.GetPlayer() && !Self.IsInCombat()
        LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
        if kSensor != None
            kSensor.OnLucyActivated()
        endif
    endif
EndEvent

Event OnCombatStateChanged(Actor akTarget, int aeCombatState)
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
    LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
    if kSensor != None
        kSensor.TriggerSnapshot("companion_hurt")
    endif
EndEvent
