Scriptname LucyCmdFollowWaitScript extends ActiveMagicEffect

Quest Property LucyQuest Auto
Potion Property CommandPotion Auto

Event OnEffectStart(Actor akTarget, Actor akCaster)
    if akTarget == Game.GetPlayer()
        if CommandPotion != None
            akTarget.AddItem(CommandPotion, 1, true)
        endif
        LucyCompanionSensorScript kSensor = LucyQuest as LucyCompanionSensorScript
        if kSensor != None
            kSensor.CommandToggleFollowWait()
        endif
    endif
EndEvent
