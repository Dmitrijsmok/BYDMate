package com.bydmate.app.service

import com.bydmate.app.BuildConfig
import com.bydmate.app.helper.HelperBinderProtocol
import org.junit.Assert.assertEquals
import org.junit.Test

class ForkIdentityTest {
    @Test fun `package and helper belong to the isolated fork`() {
        assertEquals("com.bydmate.dilink3.app", BuildConfig.APPLICATION_ID)
        assertEquals(BuildConfig.APPLICATION_ID, HelperBinderProtocol.APP_PACKAGE)
        assertEquals("bydm_d3_helper", HelperBinderProtocol.PROCESS_NAME)
        assertEquals(HelperBinderProtocol.PROCESS_NAME, HelperBinderProtocol.SERVICE_NAME)
        assertEquals("${BuildConfig.APPLICATION_ID}.helper.IHelper", HelperBinderProtocol.DESCRIPTOR)
        assertEquals("${BuildConfig.APPLICATION_ID}.helper.BINDER", HelperBinderProtocol.ACTION_BINDER)
        assertEquals("${BuildConfig.APPLICATION_ID}.action.RECOVER_START", BootReceiver.ACTION_RECOVER_START)
        assertEquals("${BuildConfig.APPLICATION_ID}/com.bydmate.app.cluster.SteeringWheelKeyService",
            HelperBinderProtocol.ACCESSIBILITY_SERVICE_COMPONENT)
        assertEquals("${BuildConfig.APPLICATION_ID}/com.bydmate.app.media.MediaSessionListenerService",
            HelperBinderProtocol.NOTIFICATION_LISTENER_COMPONENT)
    }
}
