// network.h
#pragma once
#include "state.h"

void setupWiFi();
void setupUDP();
bool receivePacket(Packet &packet);
